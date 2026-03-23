from typing import Any, Iterable


class StackIsEmpty(Exception):
    pass

class Stack:
    def __init__(self, values: Iterable[Any] = ()):
        self._stack = list(values)

    def __len__(self) -> int:
        return len(self._stack)

    def __str__(self) -> str:
        to_str = map(str, self._stack)
        return f'Stack({", ".join(to_str)})'

    def __repr__(self) -> str:
        return f'Stack({self._stack!r})'

    def __iter__(self):
        return iter(self._stack)

    def __contains__(self, value) -> bool:
        return value in self._stack

    def __getitem__(self, index) -> Any:
        return self._stack[index]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._stack.clear()
        return False

    def __eq__(self, other) -> bool:
        if not isinstance(other, Stack):
            return NotImplemented
        return self._stack == other._stack

    def push(self, value: Any) -> None:
        self._stack.append(value)

    def pop(self) -> Any:
        if not self._stack:
            raise StackIsEmpty()
        return self._stack.pop()
