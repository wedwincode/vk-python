import ctypes
import sys

from task10.mock import MockConnection


def get_raw_refcount(obj: object) -> int:
    return ctypes.c_ssize_t.from_address(id(obj)).value


class OptimizedConnection:
    __slots__ = ("id", "is_open", "metadata")

    def __init__(
        self,
        id: int,
        is_open: bool = True,
        metadata: dict | None = None,
    ) -> None:
        self.id = id
        self.is_open = is_open
        self.metadata = metadata if metadata is not None else {}


def calculate_memory_diff() -> int:
    regular = MockConnection(1)
    optimized = OptimizedConnection(1)

    return sys.getsizeof(regular) - sys.getsizeof(optimized)