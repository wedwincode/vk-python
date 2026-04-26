import asyncio
from typing import Callable, Type, Tuple, Any

async def retry_with_backoff(
    func: Callable[[], Any],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Any:
    last_exception = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt == max_attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))
            await asyncio.sleep(delay)
    raise last_exception