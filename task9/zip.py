from collections.abc import Iterable
from typing import TypeVar, overload


T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")
T4 = TypeVar("T4")


@overload
def zip(
    iter1: Iterable[T1],
    iter2: Iterable[T2],
) -> list[tuple[T1, T2]]:
    pass


@overload
def zip(
    iter1: Iterable[T1],
    iter2: Iterable[T2],
    iter3: Iterable[T3],
) -> list[tuple[T1, T2, T3]]:
    pass


@overload
def zip(
    iter1: Iterable[T1],
    iter2: Iterable[T2],
    iter3: Iterable[T3],
    iter4: Iterable[T4],
) -> list[tuple[T1, T2, T3, T4]]:
    pass


def zip(
    iter1: Iterable[T1],
    iter2: Iterable[T2],
    iter3: Iterable[T3] | None = None,
    iter4: Iterable[T4] | None = None,
) -> list[tuple[T1, T2]] | list[tuple[T1, T2, T3]] | list[tuple[T1, T2, T3, T4]]:
    pass