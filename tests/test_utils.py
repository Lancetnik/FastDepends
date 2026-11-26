from unittest.mock import AsyncMock

import pytest

from fast_depends.utils import is_coroutine_callable, run_async


def test_is_coroutine_callable() -> None:
    async def coroutine_func() -> None: ...

    assert is_coroutine_callable(coroutine_func)

    def sync_func() -> None: ...

    assert not is_coroutine_callable(sync_func)

    assert is_coroutine_callable(AsyncMock())


@pytest.mark.anyio
async def test_run_async_supports_arbitrary_callbacks():
    def sync(value):
        return value + 1

    async def async_(value):
        return value + 2

    assert await run_async(sync, 1) == 2
    assert await run_async(async_, 1) == 3
