from typing import Annotated

import pytest

from fast_depends import Depends, inject


@pytest.mark.anyio
async def test_typealiastype_depends_async() -> None:
    async def dep_func(b):
        return b

    type D = Annotated[int, Depends(dep_func)]

    @inject
    async def some_async_func(a: int, b: D) -> int:
        assert isinstance(b, int)
        return a + b

    assert await some_async_func(1, 2) == 3


def test_typealiastype_depends_sync() -> None:
    def dep_func(b):
        return b

    type D = Annotated[int, Depends(dep_func)]

    @inject
    def some_func(a: int, b: D) -> int:
        assert isinstance(b, int)
        return a + b

    assert some_func(1, 2) == 3
