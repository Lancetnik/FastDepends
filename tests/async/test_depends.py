import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from typing import Annotated
from unittest.mock import Mock

import pytest

from fast_depends import Depends, inject
from fast_depends.exceptions import ValidationError
from tests.marks import serializer


@pytest.mark.anyio
async def test_depends() -> None:
    async def dep_func(b, a=3):
        return a + b

    @inject
    async def some_func(b: int, c=Depends(dep_func)):
        return b + c

    assert (await some_func(2)) == 7


@pytest.mark.anyio
async def test_ignore_depends_if_setted_manual() -> None:
    mock = Mock()

    async def dep_func(a, b) -> int:
        mock(a, b)
        return a + b

    @inject
    async def some_func(c=Depends(dep_func)) -> int:
        return c

    assert (await some_func(c=2)) == 2
    assert not mock.called

    assert (await some_func(1, 2)) == 3
    mock.assert_called_once_with(1, 2)


@pytest.mark.anyio
async def test_empty_main_body() -> None:
    async def dep_func(a):
        return a

    @inject
    async def some_func(c=Depends(dep_func)):
        return c

    assert await some_func("1") == "1"


@pytest.mark.anyio
async def test_empty_main_body_multiple_args() -> None:
    def dep2(b):
        return b

    async def dep(a):
        return a

    @inject()
    async def handler(d=Depends(dep2), c=Depends(dep)):
        return d, c

    await handler(a=1, b=2) == (2, 1)
    await handler(1, b=2) == (2, 1)
    await handler(1, a=2) == (1, 2)
    await handler(1, 2) == (1, 1)  # all dependencies takes the first arg


@pytest.mark.anyio
async def test_sync_depends() -> None:
    def sync_dep_func(a):
        return a

    @inject
    async def some_func(a: int, b: int, c=Depends(sync_dep_func)):
        return a + b + c

    assert await some_func(1, 2) == 4


@pytest.mark.anyio
async def test_depends_annotated() -> None:
    async def dep_func(a):
        return a

    D = Annotated[int, Depends(dep_func)]

    @inject
    async def some_func(a: int, b: int, c: D):
        assert isinstance(c, int)
        return a + b + c

    @inject
    async def another_func(a: int, c: D):
        return a + c

    assert await some_func(1, 2) == 4
    assert (await another_func(3)) == 6


@pytest.mark.anyio
async def test_async_depends_annotated_str_partial() -> None:
    async def adep_func(a):
        return a

    @inject
    async def some_func(
        a: int,
        b: int,
        c: Annotated["float", Depends(adep_func)],
    ):
        return a + b + c

    @inject
    async def another_func(
        a: int,
        c: Annotated["float", Depends(adep_func)],
    ):
        return a + c

    assert await some_func(1, 2) == 4
    assert (await another_func(3)) == 6


@pytest.mark.anyio
async def test_cache() -> None:
    mock = Mock()

    async def nested_dep_func():
        mock()
        return 1000

    async def dep_func(a=Depends(nested_dep_func)):
        return a

    @inject
    async def some_func(a=Depends(dep_func), b=Depends(nested_dep_func)):
        assert a is b
        return a + b

    assert await some_func()
    mock.assert_called_once()


@pytest.mark.anyio
async def test_not_cache() -> None:
    mock = Mock()

    async def nested_dep_func():
        mock()
        return 1000

    async def dep_func(a=Depends(nested_dep_func, use_cache=False)):
        return a

    @inject
    async def some_func(
        a=Depends(dep_func, use_cache=False),
        b=Depends(nested_dep_func, use_cache=False),
    ):
        assert a is b
        return a + b

    assert await some_func()
    assert mock.call_count == 2


@pytest.mark.anyio
async def test_yield() -> None:
    mock = Mock()

    async def dep_func():
        mock()
        yield 1000
        mock.exit()

    @inject
    async def some_func(a=Depends(dep_func)):
        assert mock.called
        assert not mock.exit.called
        return a

    assert await some_func()
    mock.assert_called_once()
    mock.exit.assert_called_once()


@pytest.mark.anyio
async def test_sync_yield() -> None:
    mock = Mock()

    def sync_dep_func():
        mock()
        yield 1000
        mock.exit()

    @inject
    async def some_func(a=Depends(sync_dep_func)):
        assert mock.called
        assert not mock.exit.called
        return a

    assert await some_func()
    mock.assert_called_once()
    mock.exit.assert_called_once()


@pytest.mark.anyio
async def test_sync_yield_exception() -> None:
    mock = Mock()

    def sync_dep_func():
        mock()
        yield 1000
        raise ValueError()

    @inject
    async def some_func(a=Depends(sync_dep_func)):
        assert mock.called
        assert not mock.exit.called
        return a

    with pytest.raises(ValueError):
        await some_func()

    mock.assert_called_once()
    assert not mock.exit.called


@pytest.mark.anyio
async def test_sync_yield_exception_start() -> None:
    mock = Mock()

    def sync_dep_func():
        raise ValueError()

    @inject
    async def some_func(a=Depends(sync_dep_func)):  # pragma: no cover
        mock()
        return a

    with pytest.raises(ValueError):
        await some_func()

    assert not mock.called


@pytest.mark.anyio
async def test_sync_yield_exception_main() -> None:
    mock = Mock()

    def sync_dep_func():
        mock()
        try:
            yield 1000
        finally:
            mock.exit()

    @inject
    async def some_func(a=Depends(sync_dep_func)):
        assert mock.called
        assert not mock.exit.called
        raise ValueError()

    with pytest.raises(ValueError):
        await some_func()

    mock.assert_called_once()
    mock.exit.assert_called_once()


@pytest.mark.anyio
async def test_nested_yield_with_inject() -> None:
    async def dep_c():
        yield ["foo"]

    @inject
    async def dep_b(c=Depends(dep_c)):
        yield c

    @inject
    async def a(b=Depends(dep_b)):
        return b[0]

    assert await a() == "foo"


@pytest.mark.anyio
async def test_class_depends() -> None:
    class MyDep:
        def __init__(self, a: int):
            self.a = a

    @inject
    async def some_func(a=Depends(MyDep)):
        assert isinstance(a, MyDep)
        assert a.a == 3
        return a

    await some_func(3)


@pytest.mark.anyio
async def test_callable_class_depends() -> None:
    class MyDep:
        def __init__(self, a: int):
            self.a = a

        def __call__(self) -> int:
            return self.a

    @inject
    async def some_func(a=Depends(MyDep(3))):  # noqa: B008
        assert a == 3
        return a

    await some_func()


@pytest.mark.anyio
async def test_async_callable_class_depends() -> None:
    class MyDep:
        def __init__(self, a: int):
            self.a = a

        async def call(self) -> int:
            return self.a

    @inject
    async def some_func(a=Depends(MyDep(3).call)):  # noqa: B008
        assert a == 3
        return a

    await some_func()


@pytest.mark.anyio
async def test_not_cast_main() -> None:
    @dataclass
    class A:
        a: int

    async def dep() -> A:
        return A(a=1)

    async def get_logger() -> logging.Logger:
        return logging.getLogger(__file__)

    @inject(cast=False)
    async def some_func(
        b: str,
        a: A = Depends(dep),
        logger: logging.Logger = Depends(get_logger),
    ) -> str:
        assert a.a == 1
        assert logger
        return b

    assert (await some_func(1)) == 1


@pytest.mark.anyio
async def test_extra() -> None:
    mock = Mock()

    async def dep():
        mock.async_call()

    def sync_dep():
        mock.sync_call()

    @inject(extra_dependencies=(Depends(dep), Depends(sync_dep)))
    async def some_func():
        mock()

    await some_func(1)
    mock.assert_called_once()
    mock.async_call.assert_called_once()
    mock.sync_call.assert_called_once()


@pytest.mark.anyio
async def test_generator() -> None:
    mock = Mock()

    def sync_simple_func():
        mock.sync_simple()

    async def simple_func():
        mock.simple()

    async def func():
        mock.start()
        yield
        mock.end()

    @inject
    async def simple_func(
        a: str,
        d3=Depends(sync_simple_func),
        d2=Depends(simple_func),
        d=Depends(func),
    ):
        for _ in range(2):
            yield a

    async for i in simple_func("1"):
        mock.start.assert_called_once()
        assert not mock.end.called
        assert i == "1"

    mock.sync_simple.assert_called_once()
    mock.simple.assert_called_once()
    mock.end.assert_called_once()


@pytest.mark.anyio
async def test_partial() -> None:
    async def dep(a):
        return a

    @inject
    async def func(a=Depends(partial(dep, 10))):  # noqa D008
        return a

    assert await func() == 10


@serializer
@pytest.mark.anyio
class TestSerializer:
    @pytest.mark.anyio
    async def test_not_cast(self) -> None:
        @dataclass
        class A:
            a: int

        async def dep1() -> A:
            return {"a": 1}

        async def dep2() -> A:
            return {"a": 1}

        async def dep3() -> A:
            return 1

        async def get_logger() -> logging.Logger:
            return logging.getLogger(__file__)

        @inject
        async def some_func(
            b,
            a1: A = Depends(dep1, cast=False, cast_result=True),
            a2: A = Depends(dep2, cast=True, cast_result=False),
            a3: A = Depends(dep3, cast=False, cast_result=False),
            logger: logging.Logger = Depends(get_logger),
        ):
            assert a1.a == 1
            assert a2.a == 1
            assert a3 == 1
            assert logger
            return b

        assert (await some_func(1)) == 1

    async def test_depends_error(self) -> None:
        async def dep_func(b: dict, a: int = 3) -> float:  # pragma: no cover
            return a + b

        async def another_dep_func(b: int, a: int = 3) -> dict:  # pragma: no cover
            return a + b

        @inject
        async def some_func(
            b: int, c=Depends(dep_func), d=Depends(another_dep_func)
        ) -> int:  # pragma: no cover
            assert c is None
            return b

        with pytest.raises(ValidationError):
            assert await some_func("2")

    async def test_depends_response_cast(self) -> None:
        async def dep_func(a):
            return a

        @inject
        async def some_func(a: int, b: int, c: int = Depends(dep_func)) -> float:
            assert isinstance(c, int)
            return a + b + c

        assert await some_func("1", "2")

    async def test_async_depends_annotated_str(self) -> None:
        async def dep_func(a):
            return a

        @inject
        async def some_func(
            a: int,
            b: int,
            c: "Annotated[int, Depends(dep_func)]",
        ) -> float:
            assert isinstance(c, int)
            return a + b + c

        @inject
        async def another_func(
            a: int,
            c: "Annotated[int, Depends(dep_func)]",
        ):
            return a + c

        assert await some_func("1", "2")
        assert await another_func("3") == 6.0


@pytest.mark.anyio
async def test_default_key_value() -> None:
    async def dep(a: str = "a"):
        return a

    @inject(cast=False)
    async def func(a=Depends(dep)):
        return a

    assert await func() == "a"


@pytest.mark.anyio
async def test_asynccontextmanager() -> None:
    async def dep(a: str):
        return a

    @asynccontextmanager
    @inject
    async def func(a: str, b: str = Depends(dep)):
        yield a == b

    async with func("a") as is_equal:
        assert is_equal


@pytest.mark.anyio
async def test_solve_wrapper() -> None:
    @inject
    async def dep1(a: int):
        yield a + 1

    async def dep2(a: int):
        yield a + 2

    @inject
    async def func(a: int, b: int = Depends(dep1), c: int = Depends(dep2)):
        return a, b, c

    assert await func(1) == (1, 2, 3)
