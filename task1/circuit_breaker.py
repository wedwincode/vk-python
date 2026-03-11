import collections
import functools
import time


class NotAliveError(Exception):
    pass

def circuit_breaker(
    state_count: int,
    error_count: int,
    network_errors: list[type[Exception]],
    sleep_time_sec: int
):
    if state_count <= 10:
        raise ValueError("state_count must be greater than 10")

    if error_count >= 10:
        raise ValueError("error_count must be less than 10")

    if error_count <= 0:
        raise ValueError("error_count must be greater than 0")

    if error_count > state_count:
        raise ValueError("error_count must not be greater than state_count")

    if sleep_time_sec < 0:
        raise ValueError("sleep_time_sec must not be negative")

    if not isinstance(network_errors, list):
        raise ValueError("network_errors must be a list of exception types")

    if not network_errors:
        raise ValueError("network_errors must not be empty")

    for error in network_errors:
        if not isinstance(error, type) or not issubclass(error, Exception):
            raise ValueError("network_errors must contain exception classes")

    history = collections.deque(maxlen=state_count)
    network_errors_tuple = tuple(network_errors)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_states = list(history)[-error_count:]

            if len(last_states) == error_count and not any(last_states):
                raise NotAliveError()

            if history and history[-1] is False:
                time.sleep(sleep_time_sec)

            try:
                result = func(*args, **kwargs)
                history.append(True)
                return result
            except Exception as e:
                if isinstance(e, network_errors_tuple):
                    history.append(False)
                else:
                    raise
        return wrapper
    return decorator
