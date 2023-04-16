from unittest.mock import Mock
from typing_extensions import Annotated

import pytest
from pydantic import ValidationError

from fast_depends import inject, Depends


@pytest.mark.asyncio
async def test_depends():
    async def dep_func(b: int, a: int = 3) -> float:
        return a + b

    @inject
    async def some_func(b: int, c = Depends(dep_func)) -> int:
        assert isinstance(c, float)
        return b + c

    assert (await some_func("2")) == 7


@pytest.mark.asyncio
async def test_sync_depends():
    def dep_func(a: int) -> float:
        return a

    @inject
    async def some_func(a: int, b: int, c = Depends(dep_func)) -> str:
        assert isinstance(c, float)
        return a + b + c

    assert await some_func("1", "2")


@pytest.mark.asyncio
async def test_depends_response_cast():
    async def dep_func(a):
        return a

    @inject
    async def some_func(a: int, b: int, c: int = Depends(dep_func)) -> str:
        assert isinstance(c, int)
        return a + b + c

    assert await some_func("1", "2")


@pytest.mark.asyncio
async def test_depends_error():
    async def dep_func(b: dict, a: int = 3) -> float:  # pragma: no cover
        return a + b

    async def another_dep_func(b: int, a: int = 3) -> dict:  # pragma: no cover
        return a + b

    @inject
    async def some_func(b: int, c = Depends(dep_func), d = Depends(another_dep_func)) -> int:  # pragma: no cover
        assert c is None
        return b

    with pytest.raises(ValidationError):
        assert await some_func("2")


@pytest.mark.asyncio
async def test_depends_annotated():
    async def dep_func(a):
        return a

    D = Annotated[int, Depends(dep_func)]

    @inject
    async def some_func(a: int, b: int, c: D = None) -> str:
        assert isinstance(c, int)
        return a + b + c
    
    @inject
    async def another_func(a: int, c: D):
        return a + c

    assert await some_func("1", "2")
    assert (await another_func(3)) == 6


@pytest.mark.asyncio
async def test_cash():
    mock = Mock()

    async def nested_dep_func():
        mock()
        return 1000

    async def dep_func(a = Depends(nested_dep_func)):
        return a

    @inject
    async def some_func(a = Depends(dep_func), b = Depends(nested_dep_func)):
        assert a is b
        return a + b

    assert await some_func()
    mock.assert_called_once()


@pytest.mark.asyncio
async def test_yield():
    mock = Mock()

    async def dep_func():
        mock()
        yield 1000
        mock.exit()

    @inject
    async def some_func(a = Depends(dep_func)):
        assert mock.called
        assert not mock.exit.called
        return a

    assert await some_func()
    mock.assert_called_once()
    mock.exit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_yield():
    mock = Mock()

    def dep_func():
        mock()
        yield 1000
        mock.exit()

    @inject
    async def some_func(a = Depends(dep_func)):
        assert mock.called
        assert not mock.exit.called
        return a

    assert await some_func()
    mock.assert_called_once()
    mock.exit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_yield_exception():
    mock = Mock()

    def dep_func():
        mock()
        yield 1000
        raise ValueError()

    @inject
    async def some_func(a = Depends(dep_func)):
        assert mock.called
        assert not mock.exit.called
        return a

    with pytest.raises(ValueError):
        await some_func()

    mock.assert_called_once()
    assert not mock.exit.called


@pytest.mark.asyncio
async def test_sync_yield_exception_start():
    mock = Mock()

    def dep_func():
        raise ValueError()

    @inject
    async def some_func(a = Depends(dep_func)):  # pragma: no cover
        mock()
        return a

    with pytest.raises(ValueError):
        await some_func()

    assert not mock.called


@pytest.mark.asyncio
async def test_sync_yield_exception_main():
    mock = Mock()

    def dep_func():
        mock()
        try:
            yield 1000
        finally:
            mock.exit()

    @inject
    async def some_func(a = Depends(dep_func)):
        assert mock.called
        assert not mock.exit.called
        raise ValueError()

    with pytest.raises(ValueError):
        await some_func()

    mock.assert_called_once()
    mock.exit.assert_called_once()


@pytest.mark.asyncio
async def test_class_depends():
    class MyDep:
        def __init__(self, a: int):
            self.a = a

    @inject
    async def some_func(a = Depends(MyDep)):
        assert isinstance(a, MyDep)
        assert a.a == 3
        return a

    await some_func(3)


@pytest.mark.asyncio
async def test_callable_class_depends():
    class MyDep:
        def __init__(self, a: int):
            self.a = a
        
        def __call__(self) -> int:
            return self.a

    @inject
    async def some_func(a = Depends(MyDep(3))):
        assert a == 3
        return a

    await some_func()


@pytest.mark.asyncio
async def test_async_callable_class_depends():
    class MyDep:
        def __init__(self, a: int):
            self.a = a
        
        async def call(self) -> int:
            return self.a

    @inject
    async def some_func(a = Depends(MyDep(3).call)):
        assert a == 3
        return a

    await some_func()
