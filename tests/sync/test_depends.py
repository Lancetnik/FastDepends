import logging
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from typing import Annotated
from unittest.mock import Mock

import pytest

from fast_depends import Depends, inject
from fast_depends.exceptions import ValidationError
from tests.marks import serializer


def test_depends() -> None:
    def dep_func(b: int, a: int = 3):
        return a + b

    @inject
    def some_func(b: int, c=Depends(dep_func)):
        return b + c

    assert some_func(2) == 7


def test_empty_main_body() -> None:
    def dep_func(a):
        return a

    @inject
    def some_func(c=Depends(dep_func)):
        return c

    assert some_func(1) == 1


def test_class_depends() -> None:
    class MyDep:
        def __init__(self, a):
            self.a = a

    @inject
    def some_func(a=Depends(MyDep)):
        assert isinstance(a, MyDep)
        assert a.a == 3
        return a

    some_func(3)


def test_empty_main_body_multiple_args() -> None:
    def dep2(b):
        return b

    def dep(a):
        return a

    @inject()
    def handler(d=Depends(dep2), c=Depends(dep)):
        return d, c

    assert handler(a=1, b=2) == (2, 1)
    assert handler(1, b=2) == (2, 1)
    assert handler(1, a=2) == (1, 2)
    assert handler(1, 2) == (1, 1)  # all dependencies takes the first arg


def test_ignore_depends_if_setted_manual() -> None:
    mock = Mock()

    def dep_func(a, b) -> int:
        mock(a, b)
        return a + b

    @inject
    def some_func(c=Depends(dep_func)) -> int:
        return c

    assert some_func(c=2) == 2
    assert not mock.called

    assert some_func(1, 2) == 3
    mock.assert_called_once_with(1, 2)


def test_depends_annotated_type_str() -> None:
    def dep_func(a):
        return a

    @inject
    def some_func(
        a: int,
        b: int,
        c: Annotated["int", Depends(dep_func)],
    ):
        return a + b + c

    @inject
    def another_func(
        a: int,
        c: Annotated["int", Depends(dep_func)],
    ):
        return a + c

    assert some_func(1, 2) == 4
    assert another_func(3) == 6


def test_cache() -> None:
    mock = Mock()

    def nested_dep_func():
        mock()
        return 1000

    def dep_func(a=Depends(nested_dep_func)):
        return a

    @inject
    def some_func(
        a=Depends(dep_func),
        b=Depends(nested_dep_func),
    ):
        assert a is b
        return a + b

    some_func()
    mock.assert_called_once()


def test_not_cache() -> None:
    mock = Mock()

    def nested_dep_func():
        mock()
        return 1000

    def dep_func(a=Depends(nested_dep_func, use_cache=False)):
        return a

    @inject
    def some_func(
        a=Depends(dep_func, use_cache=False),
        b=Depends(nested_dep_func, use_cache=False),
    ):
        assert a is b
        return a + b

    some_func()
    assert mock.call_count == 2


def test_yield() -> None:
    mock = Mock()

    def dep_func():
        mock()
        yield 1000
        mock.exit()

    @inject
    def some_func(a=Depends(dep_func)):
        assert mock.called
        assert not mock.exit.called
        return a

    some_func()
    mock.assert_called_once()
    mock.exit.assert_called_once()


def test_nested_yield_with_inject() -> None:
    def dep_c():
        yield ["foo"]

    @inject
    def dep_b(c=Depends(dep_c)):
        yield c

    @inject
    def a(b=Depends(dep_b)):
        return b[0]

    assert a() == "foo"


def test_callable_class_depends() -> None:
    class MyDep:
        def __init__(self, a: int):
            self.a = a

        def __call__(self) -> int:
            return self.a

    @inject
    def some_func(a: int = Depends(MyDep(3))):  # noqa: B008
        assert a == 3
        return a

    some_func()


def test_not_cast_main() -> None:
    @dataclass
    class A:
        a: int

    def dep() -> A:
        return A(a=1)

    def get_logger() -> logging.Logger:
        return logging.getLogger(__file__)

    @inject(cast=False)
    def some_func(
        b: str,
        a: A = Depends(dep),
        logger: logging.Logger = Depends(get_logger),
    ) -> str:
        assert a.a == 1
        assert logger
        return b

    assert some_func(1) == 1


def test_extra() -> None:
    mock = Mock()

    def dep():
        mock.sync_call()

    @inject(extra_dependencies=(Depends(dep),))
    def some_func():
        mock()

    some_func()
    mock.assert_called_once()
    mock.sync_call.assert_called_once()


def test_async_extra() -> None:
    mock = Mock()

    async def dep():  # pragma: no cover
        mock.sync_call()

    with pytest.raises(AssertionError):

        @inject(extra_dependencies=(Depends(dep),))
        def some_func():  # pragma: no cover
            mock()


def test_async_depends() -> None:
    async def dep_func(a: int) -> float:  # pragma: no cover
        return a

    with pytest.raises(AssertionError):

        @inject
        def some_func(a: int, b: int, c=Depends(dep_func)) -> str:  # pragma: no cover
            return a + b + c


def test_async_extra_depends() -> None:
    async def dep_func(a: int) -> float:  # pragma: no cover
        return a

    with pytest.raises(AssertionError):

        @inject(extra_dependencies=(Depends(dep_func),))
        def some_func(a: int, b: int) -> str:  # pragma: no cover
            return a + b


def test_generator() -> None:
    mock = Mock()

    def simple_func():
        mock.simple()

    def func():
        mock.start()
        yield
        mock.end()

    @inject
    def simple_func(a: str, d2=Depends(simple_func), d=Depends(func)):
        for _ in range(2):
            yield a

    for i in simple_func("1"):
        mock.start.assert_called_once()
        assert not mock.end.called
        assert i == "1"

    mock.simple.assert_called_once()
    mock.end.assert_called_once()


def test_partial() -> None:
    def dep(a):
        return a

    @inject
    def func(a=Depends(partial(dep, 10))):  # noqa: B008
        return a

    assert func() == 10


@serializer
class TestSerializer:
    def test_not_cast(self) -> None:
        @dataclass
        class A:
            a: int

        def dep1() -> A:
            return {"a": 1}

        def dep2() -> A:
            return {"a": 1}

        def dep3() -> A:
            return 1

        def get_logger() -> logging.Logger:
            return logging.getLogger(__file__)

        @inject
        def some_func(
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

        assert some_func(1) == 1

    def test_depends_error(self) -> None:
        def dep_func(b: dict, a: int = 3) -> float:  # pragma: no cover
            return a + b

        def another_func(b: int, a: int = 3) -> dict:  # pragma: no cover
            return a + b

        @inject
        def some_func(
            b: int, c=Depends(dep_func), d=Depends(another_func)
        ) -> int:  # pragma: no cover
            assert c is None
            return b

        with pytest.raises(ValidationError):
            assert some_func("2") == 7

    def test_depends_response_cast(self) -> None:
        def dep_func(a):
            return a

        @inject
        def some_func(a: int, b: int, c: int = Depends(dep_func)) -> float:
            assert isinstance(c, int)
            assert c == a
            return a + b + c

        assert some_func("1", "2")

    def test_depends_annotated_str(self) -> None:
        def dep_func(a):
            return a

        @inject
        def some_func(
            a: int,
            b: int,
            c: "Annotated[int, Depends(dep_func)]",
        ) -> float:
            assert isinstance(c, int)
            return a + b + c

        @inject
        def another_func(
            a: int,
            c: "Annotated[int, Depends(dep_func)]",
        ):
            return a + c

        assert some_func("1", "2")
        assert another_func("3") == 6.0


def test_default_key_value() -> None:
    def dep(a: str = "a"):
        return a

    @inject(cast=False)
    def func(a=Depends(dep)):
        return a

    assert func() == "a"


def test_contextmanager() -> None:
    def dep(a: str):
        return a

    @contextmanager
    @inject
    def func(a: str, b: str = Depends(dep)):
        yield a == b

    with func("a") as is_equal:
        assert is_equal


def test_solve_wrapper() -> None:
    @inject
    def dep1(a: int) -> Generator[int, None, None]:
        yield a + 1

    def dep2(a: int) -> Generator[int, None, None]:
        yield a + 2

    @inject
    def func(a: int, b: int = Depends(dep1), c: int = Depends(dep2)):
        return a, b, c

    assert func(1) == (1, 2, 3)


def test_generator_iter() -> None:
    # ref: https://github.com/Lancetnik/FastDepends/issues/165

    def simple_dependency(a: int, b: int = 3) -> int:
        return a + b

    @inject
    def method(a: int, d: int = Depends(simple_dependency)) -> Generator[int, None, None]:
        yield from range(a + d)

    iterator = method(5)

    assert len(list(iterator)) == 13
    assert len(list(iterator)) == 0


def test_typealiastype_depends() -> None:
    def dep_func(b):
        return b

    type D = Annotated[int, Depends(dep_func)]

    @inject
    def some_func(a: int, b: D) -> int:
        assert isinstance(b, int)
        return a + b

    assert some_func(1, 2) == 3