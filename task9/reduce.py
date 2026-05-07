from collections.abc import Callable, Sequence
from typing import TypeVar, overload

T = TypeVar("T")
Accumulator = TypeVar("Accumulator")


@overload
def reduce(
    values: Sequence[T],
    func: Callable[[T, T], T],
    initial: T,
) -> T:
    pass


@overload
def reduce(
    values: Sequence[T],
    func: Callable[[Accumulator, T], Accumulator],
    initial: Accumulator,
) -> Accumulator:
    pass


def reduce(
    values: Sequence[T],
    func: Callable[[T | Accumulator, T], T | Accumulator],
    initial: T | Accumulator,
) -> T | Accumulator:
    pass