import heapq
import json
import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from itertools import count
from pathlib import Path
from typing import Iterator


class EventType(str, Enum):
    ERROR = "ERROR"
    INFO = "INFO"
    DEBUG = "DEBUG"


@dataclass(slots=True)
class Event:
    TIME_FMT = "%Y-%m-%d %H:%M:%S"

    service: str
    dt: datetime
    event_type: EventType
    message: str
    params: dict[str, str]

    @classmethod
    def from_json(cls, service: str, s: str) -> "Event":
        try:
            data = json.loads(s)
            msg = data["message"]
            params = data["params"]
            if not isinstance(msg, str):
                raise ValueError("message should be a string")
            if not isinstance(params, dict):
                raise ValueError("params should be a dictionary")
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in params.items()):
                raise ValueError("params keys and values should be strings")
            return cls(
                service=service,
                dt=datetime.strptime(data["datetime"], cls.TIME_FMT),
                event_type=EventType(data["event_type"]),
                message=msg.format(**params),
                params=params,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as err:
            raise ValueError(f"invalid event: {err}") from err


class JournalHandler:
    NAME_RE = re.compile(r"^(?P<service>.+)_(?P<hour>\d{10})\.log$")
    HOUR_FMT = "%Y%m%d%H"

    def __init__(self, log_dir: str | Path) -> None:
        self.log_dir = Path(log_dir)
        if not self.log_dir.is_dir():
            raise NotADirectoryError("log directory not found")
        self._meta: dict[Path, tuple[str, datetime]] = {}
        self._errors: dict[Path, tuple[str, list[datetime], datetime | None]] = {}

    def get_last_events(self, n: int) -> list[Event]:
        return self._last(n)

    def get_last_events_by_param(self, n: int, value: str) -> list[Event]:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("param_value should not be empty")
        return self._last(n, value=value.strip())

    def get_last_events_by_service(self, n: int, service: str) -> list[Event]:
        if not isinstance(service, str) or not service.strip():
            raise ValueError("service should not be empty")
        return self._last(n, service=service.strip())

    def get_error_counts_by_service(self, start: datetime, end: datetime) -> dict[str, int]:
        if start > end:
            raise ValueError("time_start should be earlier than time_end")
        res: dict[str, int] = {}
        for path in self._files(start=start, end=end):
            service, times, _ = self._error_stat(path)
            cnt = bisect_right(times, end) - bisect_left(times, start)
            if cnt:
                res[service] = res.get(service, 0) + cnt
        return res

    def get_last_errors_dates_by_service(self) -> dict[str, datetime]:
        res: dict[str, datetime] = {}
        for path in self._files():
            service, _, last = self._error_stat(path)
            if last is not None and (service not in res or last > res[service]):
                res[service] = last
        return res

    def _last(self, n: int, service: str | None = None, value: str | None = None) -> list[Event]:
        if n < 1:
            raise ValueError("n should be greater than 0")
        res: list[Event] = []
        for event in self._iter_last(service, value):
            res.append(event)
            if len(res) == n:
                break
        return res

    def _iter_last(self, service: str | None = None, value: str | None = None) -> Iterator[Event]:
        its = [self._iter_events_rev(p) for p in self._files(service=service)]
        heap: list[tuple[float, int, Event, Iterator[Event]]] = []
        seq = count()

        for it in its:
            try:
                ev = next(it)
            except StopIteration:
                continue
            heapq.heappush(heap, (-ev.dt.timestamp(), next(seq), ev, it))

        while heap:
            _, _, ev, it = heapq.heappop(heap)
            if value is None or value in ev.params.values():
                yield ev
            try:
                nxt = next(it)
            except StopIteration:
                continue
            heapq.heappush(heap, (-nxt.dt.timestamp(), next(seq), nxt, it))

    def _files(
        self,
        service: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Path]:
        items: list[tuple[datetime, Path]] = []
        start_h = start and start.replace(minute=0, second=0, microsecond=0)
        end_h = end and end.replace(minute=0, second=0, microsecond=0)

        for path in self.log_dir.iterdir():
            if not path.is_file():
                continue
            try:
                srv, hour = self._file_meta(path)
            except ValueError:
                continue
            if service is not None and srv != service:
                continue
            if start_h is not None and hour < start_h:
                continue
            if end_h is not None and hour > end_h:
                continue
            items.append((hour, path))

        items.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in items]

    def _file_meta(self, path: Path) -> tuple[str, datetime]:
        if path in self._meta:
            return self._meta[path]
        m = self.NAME_RE.match(path.name)
        if m is None:
            raise ValueError(f"invalid file name: {path.name}")
        try:
            meta = (m.group("service"), datetime.strptime(m.group("hour"), self.HOUR_FMT))
        except ValueError as err:
            raise ValueError(f"invalid file name: {path.name}") from err
        self._meta[path] = meta
        return meta

    def _error_stat(self, path: Path) -> tuple[str, list[datetime], datetime | None]:
        if path in self._errors:
            return self._errors[path]
        service, hour = self._file_meta(path)
        times: list[datetime] = []
        for line in self._iter_lines(path):
            ev = Event.from_json(service, line)
            if ev.dt.strftime(self.HOUR_FMT) != hour.strftime(self.HOUR_FMT):
                raise ValueError(f"event datetime does not match file hour: {path.name}")
            if ev.event_type is EventType.ERROR:
                times.append(ev.dt)
        stat = (service, times, times[-1] if times else None)
        self._errors[path] = stat
        return stat

    def _iter_events_rev(self, path: Path) -> Iterator[Event]:
        service, hour = self._file_meta(path)
        for line in self._iter_lines(path, True):
            ev = Event.from_json(service, line)
            if ev.dt.strftime(self.HOUR_FMT) != hour.strftime(self.HOUR_FMT):
                raise ValueError(f"event datetime does not match file hour: {path.name}")
            yield ev

    @staticmethod
    def _iter_lines(path: Path, rev: bool = False, chunk: int = 4096) -> Iterator[str]:
        with path.open("rb") as f:
            if not rev:
                for line in f:
                    line = line.rstrip(b"\n")
                    if line:
                        try:
                            yield line.decode()
                        except UnicodeDecodeError as err:
                            raise ValueError(f"invalid utf-8 in file {path}") from err
                return

            f.seek(0, 2)
            pos = f.tell()
            buf = b""
            while pos > 0:
                size = min(chunk, pos)
                pos -= size
                f.seek(pos)
                buf = f.read(size) + buf
                parts = buf.split(b"\n")
                buf = parts[0]
                for line in reversed(parts[1:]):
                    if line:
                        try:
                            yield line.decode()
                        except UnicodeDecodeError as err:
                            raise ValueError(f"invalid utf-8 in file {path}") from err
            if buf:
                try:
                    yield buf.decode()
                except UnicodeDecodeError as err:
                    raise ValueError(f"invalid utf-8 in file {path}") from err

journal = JournalHandler("logs")
res = journal.get_last_events_by_service(n=3, service="backend")
print(journal.get_error_counts_by_service(start=datetime(2025, 1, 1), end=datetime(2027, 1, 1)))
print(journal.get_last_errors_dates_by_service())
for e in res:
    print(e)