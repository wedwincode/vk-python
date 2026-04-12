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
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    service: str
    dt: datetime
    event_type: EventType
    message: str
    params: dict[str, str]

    @classmethod
    def from_json(cls, service: str, json_str: str) -> "Event":
        if not isinstance(service, str) or not service.strip():
            raise ValueError("service should not be empty")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as err:
            raise ValueError(f"invalid json: {err}") from err
        try:
            raw_datetime = data["datetime"]
            raw_event_type = data["event_type"]
            message = data["message"]
            params = data["params"]
        except KeyError as err:
            raise ValueError(f"missing required field: {err}") from err

        if not isinstance(message, str):
            raise ValueError("message should be a string")
        if not isinstance(params, dict):
            raise ValueError("params should be a dictionary")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in params.items()):
            raise ValueError("params keys and values should be strings")
        try:
            dt = datetime.strptime(raw_datetime, cls.DATETIME_FORMAT)
        except ValueError as err:
            raise ValueError(f"invalid datetime format: {err}") from err
        try:
            event_type = EventType(raw_event_type)
        except ValueError as err:
            raise ValueError(f"invalid event_type: {raw_event_type}") from err
        try:
            message = message.format(**params)
        except KeyError as err:
            raise ValueError(f"missing param for message interpolation: {err}") from err

        return cls(service=service, dt=dt, event_type=event_type, message=message, params=params)

@dataclass(slots=True)
class FileErrorStats:
    service: str
    file_hour: datetime
    error_times: list[datetime]
    last_error_dt: datetime | None

class JournalHandler:
    FILE_NAME_PATTERN = re.compile(r"^(?P<service>.+)_(?P<timestamp>\d{10})\.log$")
    FILE_TIMESTAMP_FORMAT = "%Y%m%d%H"

    def __init__(self, log_dir: str | Path) -> None:
        self.log_dir = Path(log_dir)

        if not self.log_dir.exists() or not self.log_dir.is_dir():
            raise NotADirectoryError("log directory not found")

        self._file_meta_cache: dict[Path, tuple[str, datetime]] = {}
        self._file_error_stats_cache: dict[Path, FileErrorStats] = {}

    def get_last_events(self, n: int) -> list[Event]:
        return self._get_last_events_list(n=n)

    def get_last_events_by_param(self, n: int, param_value: str) -> list[Event]:
        if not isinstance(param_value, str) or not param_value.strip():
            raise ValueError("param_value should not be empty")

        return self._get_last_events_list(n=n, param_value=param_value.strip())

    def get_last_events_by_service(self, n: int, service: str) -> list[Event]:
        if not isinstance(service, str) or not service.strip():
            raise ValueError("service should not be empty")

        return self._get_last_events_list(n=n, service=service.strip())

    def get_errors_counts_by_service(self, time_start: datetime, time_end: datetime) -> dict[str, int]:
        if time_start > time_end:
            raise ValueError("time_start should be earlier than time_end")

        result: dict[str, int] = {}
        for file_path in self._get_files_for_range(time_start, time_end):
            stats = self._get_or_build_file_error_stats(file_path)
            left = bisect_left(stats.error_times, time_start)
            right = bisect_right(stats.error_times, time_end)
            count_in_range = right - left
            if count_in_range > 0:
                result[stats.service] = result.get(stats.service, 0) + count_in_range

        return result

    def get_last_errors_dates_by_service(self) -> dict[str, datetime]:
        result: dict[str, datetime] = {}
        for file_path in self._get_files():
            stats = self._get_or_build_file_error_stats(file_path)
            if stats.last_error_dt is None:
                continue
            current = result.get(stats.service)
            if current is None or stats.last_error_dt > current:
                result[stats.service] = stats.last_error_dt

        return result

    def _get_last_events_list(self, n: int, service: str | None = None, param_value: str | None = None) -> list[Event]:
        if n < 1:
            raise ValueError("n should be greater than 0")

        events: list[Event] = []
        for event in self._get_last_events_iterator(service=service, param_value=param_value):
            events.append(event)
            if len(events) == n:
                break

        return events

    def _get_last_events_iterator(self, service: str | None = None, param_value: str | None = None) -> Iterator[Event]:
        if service is not None and not service.strip():
            raise ValueError("service should not be empty")
        if param_value is not None and not param_value.strip():
            raise ValueError("param_value should not be empty")

        iterators: list[Iterator[Event]] = []
        for file_path in self._get_files(service=service):
            iterators.append(self._iter_events_reversed(file_path))
        heap: list[tuple[float, int, Event, Iterator[Event]]] = []
        sequence = count()
        for iterator in iterators:
            try:
                event = next(iterator)
            except StopIteration:
                continue
            heapq.heappush(heap, (-event.dt.timestamp(), next(sequence), event, iterator))
        while heap:
            _, _, event, iterator = heapq.heappop(heap)
            if param_value is None or param_value in event.params.values():
                yield event
            try:
                next_event = next(iterator)
            except StopIteration:
                continue

            heapq.heappush(heap, (-next_event.dt.timestamp(), next(sequence), next_event, iterator))

    def _get_files(self, service: str | None = None) -> list[Path]:
        files_with_timestamps: list[tuple[datetime, Path]] = []
        for file_path in self.log_dir.iterdir():
            if not file_path.is_file():
                continue
            try:
                file_service, file_timestamp = self._get_file_meta(file_path)
            except ValueError:
                continue
            if service is not None and file_service != service:
                continue
            files_with_timestamps.append((file_timestamp, file_path))

        files_with_timestamps.sort(key=lambda item: item[0], reverse=True)
        return [file_path for _, file_path in files_with_timestamps]

    def _get_files_for_range(self, time_start: datetime, time_end: datetime) -> list[Path]:
        relevant_files: list[tuple[datetime, Path]] = []
        start_hour = time_start.replace(minute=0, second=0, microsecond=0)
        end_hour = time_end.replace(minute=0, second=0, microsecond=0)

        for file_path in self.log_dir.iterdir():
            if not file_path.is_file():
                continue
            try:
                _, file_hour = self._get_file_meta(file_path)
            except ValueError:
                continue
            if start_hour <= file_hour <= end_hour:
                relevant_files.append((file_hour, file_path))

        relevant_files.sort(key=lambda item: item[0], reverse=True)
        return [file_path for _, file_path in relevant_files]

    def _get_or_build_file_error_stats(self, file_path: Path) -> FileErrorStats:
        cached = self._file_error_stats_cache.get(file_path)
        if cached is not None:
            return cached

        service, file_hour = self._get_file_meta(file_path)
        error_times: list[datetime] = []
        for line in self._iter_lines(file_path):
            event = Event.from_json(service, line)
            if event.dt.strftime(self.FILE_TIMESTAMP_FORMAT) != file_hour.strftime(self.FILE_TIMESTAMP_FORMAT):
                raise ValueError(f"event datetime does not match file hour: {file_path.name}")
            if event.event_type is EventType.ERROR:
                error_times.append(event.dt)
        last_error_dt = error_times[-1] if error_times else None

        stats = FileErrorStats(service, file_hour, error_times, last_error_dt)
        self._file_error_stats_cache[file_path] = stats
        return stats

    def _get_file_meta(self, file_path: Path) -> tuple[str, datetime]:
        cached = self._file_meta_cache.get(file_path)
        if cached is not None:
            return cached

        match = self.FILE_NAME_PATTERN.match(file_path.name)
        if match is None:
            raise ValueError(f"invalid file name: {file_path.name}")
        try:
            file_timestamp = datetime.strptime(match.group("timestamp"), self.FILE_TIMESTAMP_FORMAT)
        except ValueError as err:
            raise ValueError(f"invalid timestamp in file name: {file_path.name}") from err

        result = (match.group("service"), file_timestamp)
        self._file_meta_cache[file_path] = result
        return result

    def _iter_events_reversed(self, file_path: Path) -> Iterator[Event]:
        service, file_dt = self._get_file_meta(file_path)
        for line in self._iter_lines_reversed(file_path):
            event = Event.from_json(service, line)
            if event.dt.strftime(self.FILE_TIMESTAMP_FORMAT) != file_dt.strftime(self.FILE_TIMESTAMP_FORMAT):
                raise ValueError(f"event datetime does not match file hour: {file_path.name}")
            yield event

    @staticmethod
    def _iter_lines(file_path: Path) -> Iterator[str]:
        with file_path.open("rb") as file:
            for line in file:
                line = line.rstrip(b"\n")
                if not line:
                    continue
                try:
                    yield line.decode("utf-8")
                except UnicodeDecodeError as err:
                    raise ValueError(f"invalid utf-8 in file {file_path}") from err

    @staticmethod
    def _iter_lines_reversed(file_path: Path, chunk_size: int = 4096) -> Iterator[str]:
        with file_path.open("rb") as file:
            file.seek(0, 2)
            position = file.tell()
            buffer = b""

            while position > 0:
                read_size = min(chunk_size, position)
                position -= read_size
                file.seek(position)
                chunk = file.read(read_size)
                buffer = chunk + buffer

                lines = buffer.split(b"\n")
                buffer = lines[0]

                for line in reversed(lines[1:]):
                    if line:
                        try:
                            yield line.decode("utf-8")
                        except UnicodeDecodeError as err:
                            raise ValueError(f"invalid utf-8 in file {file_path}") from err

            if buffer:
                try:
                    yield buffer.decode("utf-8")
                except UnicodeDecodeError as err:
                    raise ValueError(f"invalid utf-8 in file {file_path}") from err

journal = JournalHandler("logs")
res = journal.get_last_events_by_service(n=3, service="backend")
print(journal.get_errors_counts_by_service(time_start=datetime(2025, 1, 1), time_end=datetime(2027, 1, 1)))
print(journal.get_last_errors_dates_by_service())
for e in res:
    print(e)