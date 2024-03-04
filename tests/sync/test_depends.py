import logging
from dataclasses import dataclass
from functools import partial
from unittest.mock import Mock

import pytest
from typing_extensions import Annotated

try:
    from pydantic import ValidationError
except ImportError:
    ValidationError = None

from fast_depends import Depends, inject
from tests.marks import HAS_PYDANTIC, pydantic


@pydantic
def test_depends():
    def dep_func(b: int, a: int = 3) -> float:
        return a + b

    @inject
    def some_func(b: int, c=Depends(dep_func)) -> int:
        assert isinstance(c, float)
        return b + c

    assert some_func("2") == 7


def test_empty_main_body():
    def dep_func(a):
        return a + 1

    @inject
    def some_func(c=Depends(dep_func)):
        assert c == 2

    some_func(1)


def test_empty_main_body_multiple_args():
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


def test_ignore_depends_if_setted_manual():
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


def test_depends_error():
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


def test_depends_response_cast():
    def dep_func(a):
        return a

    @inject
    def some_func(a: int, b: int, c: int = Depends(dep_func)) -> float:
        assert isinstance(c, int)
        return a + b + c

    assert some_func("1", "2")


def test_depends_annotated():
    def dep_func(a):
        return a

    D = Annotated[int, Depends(dep_func)]

    @inject
    def some_func(a: int, b: int, c: D = None) -> float:
        assert isinstance(c, int)
        return a + b + c

    @inject
    def another_func(a: int, c: D):
        return a + c

    assert some_func("1", "2")
    assert another_func("3") == 6.0


def test_depends_annotated_str():
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


def test_depends_annotated_str_partial():
    def dep_func(a):
        return a

    @inject
    def some_func(
        a: int,
        b: int,
        c: Annotated["float", Depends(dep_func)],
    ) -> float:
        assert isinstance(c, float)
        return a + b + c

    @inject
    def another_func(
        a: int,
        c: Annotated["float", Depends(dep_func)],
    ):
        return a + c

    assert some_func("1", "2")
    assert another_func("3") == 6.0


def test_cache():
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


def test_not_cache():
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


def test_yield():
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


def test_class_depends():
    class MyDep:
        def __init__(self, a: int):
            self.a = a

    @inject
    def some_func(a=Depends(MyDep)):
        assert isinstance(a, MyDep)
        assert a.a == 3
        return a

    some_func(3)


def test_callable_class_depends():
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


def test_not_cast():
    @dataclass
    class A:
        a: int

    def dep() -> A:
        return A(a=1)

    def get_logger() -> logging.Logger:
        return logging.getLogger(__file__)

    @inject
    def some_func(
        b,
        a: A = Depends(dep, cast=False),
        logger: logging.Logger = Depends(get_logger, cast=False),
    ):
        assert a.a == 1
        assert logger
        return b

    assert some_func(1) == 1


def test_not_cast_main():
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


def test_extra():
    mock = Mock()

    def dep():
        mock.sync_call()

    @inject(extra_dependencies=(Depends(dep),))
    def some_func():
        mock()

    some_func()
    mock.assert_called_once()
    mock.sync_call.assert_called_once()


def test_async_extra():
    mock = Mock()

    async def dep():  # pragma: no cover
        mock.sync_call()

    with pytest.raises(AssertionError):

        @inject(extra_dependencies=(Depends(dep),))
        def some_func():  # pragma: no cover
            mock()


def test_async_depends():
    async def dep_func(a: int) -> float:  # pragma: no cover
        return a

    with pytest.raises(AssertionError):

        @inject
        def some_func(a: int, b: int, c=Depends(dep_func)) -> str:  # pragma: no cover
            return a + b + c


def test_generator():
    mock = Mock()

    def func():
        mock.start()
        yield
        mock.end()

    @inject
    def simple_func(a: str, d=Depends(func)) -> int:
        for _ in range(2):
            yield a

    for i in simple_func("1"):
        mock.start.assert_called_once()
        assert not mock.end.called
        assert i == (1 if HAS_PYDANTIC else "1")

    mock.end.assert_called_once()


def test_partial():
    def dep(a):
        return a

    @inject
    def func(a=Depends(partial(dep, 10))):  # noqa: B008
        return a

    assert func() == 10
