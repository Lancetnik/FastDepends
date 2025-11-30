from unittest.mock import AsyncMock

from fast_depends.utils import is_coroutine_callable


def test_is_coroutine_callable() -> None:
    async def coroutine_func() -> int:
        return 1

    assert is_coroutine_callable(coroutine_func)

    def sync_func() -> int:
        return 1

    assert not is_coroutine_callable(sync_func)

    assert is_coroutine_callable(AsyncMock())
