import heapq
import json
import re
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

# 3) Получение информации об ошибках (event_type=’ERROR’)
# Реализовать получение статистики об ошибках
# - Реализуйте метод получения количества ошибок в разрезе сервисов за переданный диапазон времени. Задействуйте кеширование.
# - Реализуйте метод получения даты последней ошибки по каждому сервису

class JournalHandler:
    FILE_NAME_PATTERN = re.compile(r"^(?P<service>.+)_(?P<timestamp>\d{10})\.log$")
    FILE_TIMESTAMP_FORMAT = "%Y%m%d%H"

    def __init__(self, log_dir: str | Path) -> None:
        self.log_dir = Path(log_dir)

        if not self.log_dir.exists() or not self.log_dir.is_dir():
            raise NotADirectoryError("log directory not found")

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
            raise ValueError("start time should be earlier than end time")

        it = self._get_last_events_iterator()
        errors_by_service: dict[str, int] = {}

        while True:
            try:
                event = next(it)
                if time_start <= event.dt <= time_end and event.event_type is EventType.ERROR:
                    if not errors_by_service.get(event.service):
                        errors_by_service[event.service] = 0
                    errors_by_service[event.service] += 1
            except StopIteration:
                break

        return errors_by_service

    def get_last_errors_dates_by_service(self) -> dict[str, datetime]:
        it = self._get_last_events_iterator()
        dates_by_service: dict[str, datetime] = {}

        while True:
            try:
                event = next(it)
                if event.event_type is EventType.ERROR and not dates_by_service.get(event.service):
                    dates_by_service[event.service] = event.dt
            except StopIteration:
                break

        return dates_by_service

    def _get_last_events_list(self, n: int, service: str | None = None, param_value: str | None = None) -> list[Event]:
        if n < 1:
            raise ValueError("n should be greater than 0")

        events: list[Event] = []
        it = self._get_last_events_iterator(service=service, param_value=param_value)
        while len(events) < n:
            try:
                events.append(next(it))
            except StopIteration:
                break

        return events

    def _get_last_events_iterator(self, service: str | None = None, param_value: str | None = None) -> Iterator[Event]:
        if service and not service.strip():
            raise ValueError("service should not be empty")
        if param_value and not param_value.strip():
            raise ValueError("param should not be empty")

        iterators: list[Iterator[Event]] = []

        for file in self._get_files(service=service):
            iterator = self._iter_events_reversed(file)
            iterators.append(iterator)

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

        for file in self.log_dir.iterdir():
            if not file.is_file():
                continue

            if service is not None and self._extract_file_service(file) != service.strip():
                continue

            files_with_timestamps.append((self._extract_file_timestamp(file), file))

        files_with_timestamps.sort(key=lambda item: item[0], reverse=True)
        return [file for _, file in files_with_timestamps]

    def _iter_events_reversed(self, file_path: Path) -> Iterator[Event]:
        file_dt = self._extract_file_timestamp(file_path)
        service = self._extract_file_service(file_path)

        for line in self._iter_lines_reversed(file_path):
            event = Event.from_json(service, line)

            if event.dt.strftime(self.FILE_TIMESTAMP_FORMAT) != file_dt.strftime(self.FILE_TIMESTAMP_FORMAT):
                raise ValueError(f"event datetime does not match file hour: {file_path.name}")

            yield event

    def _extract_file_service(self, file_path: Path) -> str:
        match = self.FILE_NAME_PATTERN.match(file_path.name)
        if match is None:
            raise ValueError(f"invalid file name: {file_path.name}")

        return str(match.group("service"))

    def _extract_file_timestamp(self, file_path: Path) -> datetime:
        match = self.FILE_NAME_PATTERN.match(file_path.name)
        if match is None:
            raise ValueError(f"invalid file name: {file_path.name}")

        try:
            return datetime.strptime(match.group("timestamp"), self.FILE_TIMESTAMP_FORMAT)
        except ValueError as err:
            raise ValueError(f"invalid timestamp in file name: {file_path.name}") from err

    @staticmethod
    def _iter_lines_reversed(file: Path, chunk_size: int = 4096) -> Iterator[str]:
        with file.open("rb") as f:
            f.seek(0, 2)
            position = f.tell()
            buffer = b""

            while position > 0:
                read_size = min(chunk_size, position)
                position -= read_size
                f.seek(position)
                chunk = f.read(read_size)
                buffer = chunk + buffer

                lines = buffer.split(b"\n")
                buffer = lines[0]

                for line in reversed(lines[1:]):
                    if line:
                        try:
                            yield line.decode("utf-8")
                        except UnicodeDecodeError as err:
                            raise ValueError(f"invalid utf-8 in file {file}") from err

            if buffer:
                try:
                    yield buffer.decode("utf-8")
                except UnicodeDecodeError as err:
                    raise ValueError(f"invalid utf-8 in file {file}") from err


journal = JournalHandler("logs")
res = journal.get_last_events_by_service(n=3, service="backend")
print(journal.get_errors_counts_by_service(time_start=datetime(2025, 1, 1), time_end=datetime(2027, 1, 1)))
print(journal.get_last_errors_dates_by_service())
for e in res:
    print(e)

# for _ in range(10):
#     time.sleep(1)
#     e = Event(datetime.now(), EventType.INFO, "test message param1 hello param2 world", {"param1": "aaa", "param2": "bbb"})
#     print(json.dumps(e.__dict__))

