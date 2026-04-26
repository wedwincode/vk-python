import asyncio
from unittest.mock import AsyncMock

import pytest

from task8.async_function import retry_with_backoff


@pytest.fixture
def mock_success_func():
    return AsyncMock(return_value="ok")


@pytest.fixture
def mock_fail_then_success_func():
    mock = AsyncMock(
        side_effect=[
            ValueError("first"),
            ValueError("second"),
            "ok",
        ]
    )
    return mock


@pytest.mark.asyncio
async def test_retry_success_without_retries(monkeypatch, mock_success_func):
    mocked_sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", mocked_sleep)

    result = await retry_with_backoff(mock_success_func)

    assert result == "ok"
    assert mock_success_func.await_count == 1
    mocked_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_fail_then_success(monkeypatch, mock_fail_then_success_func):
    mocked_sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", mocked_sleep)

    result = await retry_with_backoff(
        mock_fail_then_success_func,
        max_attempts=3,
        base_delay=1.0,
        exceptions=(ValueError,),
    )

    assert result == "ok"
    assert mock_fail_then_success_func.await_count == 3
    assert mocked_sleep.await_count == 2
    assert mocked_sleep.await_args_list[0].args == (1.0,)
    assert mocked_sleep.await_args_list[1].args == (2.0,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_delay, expected_delays",
    [
        (1.0, [1.0, 2.0]),
        (0.5, [0.5, 1.0]),
        (2.0, [2.0, 4.0]),
    ],
)
async def test_retry_backoff_delays(
    monkeypatch,
    mock_fail_then_success_func,
    base_delay,
    expected_delays,
):
    mocked_sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", mocked_sleep)

    result = await retry_with_backoff(
        mock_fail_then_success_func,
        max_attempts=3,
        base_delay=base_delay,
        exceptions=(ValueError,),
    )

    assert result == "ok"
    assert mocked_sleep.await_count == len(expected_delays)

    actual_delays = [
        call.args[0]
        for call in mocked_sleep.await_args_list
    ]

    assert actual_delays == expected_delays


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exceptions_list, occurred_exceptions_list, expected_exception",
    [
        (
            (ValueError,),
            [ValueError("first"), ValueError("last")],
            ValueError,
        ),
        (
            (ConnectionError,),
            [ConnectionError("first"), ConnectionError("last")],
            ConnectionError,
        ),
        (
            (RuntimeError,),
            [RuntimeError("first"), RuntimeError("last")],
            RuntimeError,
        ),
    ],
)
async def test_retry_all_failures(
    monkeypatch,
    exceptions_list,
    occurred_exceptions_list,
    expected_exception,
):
    mocked_sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", mocked_sleep)

    failing_func = AsyncMock(side_effect=occurred_exceptions_list)

    with pytest.raises(expected_exception) as exc_info:
        await retry_with_backoff(
            failing_func,
            max_attempts=len(occurred_exceptions_list),
            base_delay=1.0,
            exceptions=exceptions_list,
        )

    assert exc_info.value is occurred_exceptions_list[-1]
    assert failing_func.await_count == len(occurred_exceptions_list)
    assert mocked_sleep.await_count == len(occurred_exceptions_list) - 1
