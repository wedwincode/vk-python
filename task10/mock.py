from __future__ import annotations

import sys


class MockConnection:
    def __init__(
        self,
        id: int,
        is_open: bool = True,
        metadata: dict | None = None,
    ) -> None:
        self.id = id
        self.is_open = is_open
        self.metadata = metadata if metadata is not None else {}

    def __enter__(self) -> "MockConnection":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        self.is_open = False
        self.metadata.clear()


def show_refcount_steps(obj: object) -> tuple[int, int, int]:
    first = sys.getrefcount(obj)

    ref = obj
    second = sys.getrefcount(obj)

    del ref
    third = sys.getrefcount(obj)

    return first, second, third
