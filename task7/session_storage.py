import dataclasses
import datetime
import typing
import weakref


class UnknownUser(Exception):
    pass


@dataclasses.dataclass()
class Session:
    user_id: int
    logged_in: datetime.datetime = dataclasses.field(default_factory=datetime.datetime.now)
    logged_out: typing.Optional[datetime.datetime] = None

class UserSessions:
    def __init__(self) -> None:
        self._user_id = None
        self._sessions = weakref.WeakSet()

    def add_session(self, session: Session) -> None:
        if self._user_id is None:
            self._user_id = session.user_id

        if self._user_id != session.user_id:
            raise UnknownUser

        self._sessions.add(session)

    def __len__(self) -> int:
        return len(self._sessions)


# user_sessions = UserSessions()
#
# session1 = Session(user_id=1)
# session2 = Session(user_id=1)
#
# user_sessions.add_session(session1)
# user_sessions.add_session(session2)
#
# try:
#     user_sessions.add_session(Session(user_id=2))
# except UnknownUser:
#     pass
#
# assert len(user_sessions) == 2
#
# del session1
# del session2
#
# assert len(user_sessions) == 0

class SessionsCache:

    def __init__(self) -> None:
        self._sessions = weakref.WeakValueDictionary()
        self._hit_count = 0

    @property
    def hit_count(self) -> int:
        return self._hit_count

    def get_session(self, user_id: int) -> Session:
        session = self._sessions.get(user_id)

        if session is not None:
            self._hit_count += 1
            return session

        session = Session(user_id)
        self._sessions[user_id] = session
        return session

    def __len__(self) -> int:
        return len(self._sessions)


# cache = SessionsCache()
#
# session1 = cache.get_session(1)
# session2 = cache.get_session(2)
#
# assert session1.user_id == 1
# assert session2.user_id == 2
#
# assert len(cache) == 2
#
# assert cache.hit_count == 0
# cache.get_session(1)
# cache.get_session(1)
# assert cache.hit_count == 2
#
# del session1
# del session2
#
# assert len(cache) == 0

class SessionManager:

    def __init__(self) -> None:
        self._sessions: list[Session] = []

        self._finalizer = weakref.finalize(
            self,
            self._close_all_sessions,
            self._sessions,
        )

    def open_session(self, user_id: int) -> Session:
        session = Session(user_id)
        self._sessions.append(session)
        return session

    @staticmethod
    def _close_all_sessions(sessions: list[Session]) -> None:
        logout_time = datetime.datetime.now()
        for session in sessions:
            session.logged_out = logout_time

manager = SessionManager()

session1 = manager.open_session(1)
session2 = manager.open_session(2)

assert session1.logged_out is None
assert session2.logged_out is None

del manager

assert session1.logged_out is not None
assert session2.logged_out is not None