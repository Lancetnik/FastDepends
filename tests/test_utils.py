from unittest.mock import AsyncMock

from fast_depends.utils import is_coroutine_callable


def test_is_coroutine_callable() -> None:
    async def coroutine_func() -> None: ...

    assert is_coroutine_callable(coroutine_func)

    def sync_func() -> None: ...

    assert not is_coroutine_callable(sync_func)

    assert is_coroutine_callable(AsyncMock())
