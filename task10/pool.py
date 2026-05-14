import weakref

from task10.mock import MockConnection


class ConnectionPool:
    def __init__(self) -> None:
        self._registry = weakref.WeakSet()

    def register(self, conn: MockConnection) -> None:
        self._registry.add(conn)

    def get_active(self) -> list[MockConnection]:
        return [conn for conn in self._registry if conn.is_open]


def verify_weakset_behavior() -> tuple[int, int]:
    pool = ConnectionPool()

    conn = MockConnection(1, metadata={"host": "localhost"})
    pool.register(conn)

    before_delete = len(pool.get_active())

    del conn

    after_delete = len(pool.get_active())

    return before_delete, after_delete
