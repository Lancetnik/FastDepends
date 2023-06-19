from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from typing_extensions import Annotated

from fast_depends import Depends, inject


def test_depends():
    def dep_func(b: int, a: int = 3) -> float:
        return a + b

    @inject
    def some_func(b: int, c=Depends(dep_func)) -> int:
        assert isinstance(c, float)
        return b + c

    assert some_func("2") == 7


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


def test_async_depends():
    async def dep_func(a: int) -> float:  # pragma: no cover
        return a

    with pytest.raises(AssertionError):

        @inject
        def some_func(a: int, b: int, c=Depends(dep_func)) -> str:  # pragma: no cover
            return a + b + c


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


def test_cash():
    mock = Mock()

    def nested_dep_func():
        mock()
        return 1000

    def dep_func(a=Depends(nested_dep_func)):
        return a

    @inject
    def some_func(a=Depends(dep_func), b=Depends(nested_dep_func)):
        assert a is b
        return a + b

    some_func()
    mock.assert_called_once()


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
    def some_func(a: int = Depends(MyDep(3))):
        assert a == 3
        return a

    some_func()
