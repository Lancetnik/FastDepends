from typing import Dict, Iterator, Tuple

import pytest

from fast_depends import inject
from fast_depends.exceptions import ValidationError
from tests.marks import serializer


def test_not_annotated():
    @inject
    def some_func(a, b):
        return a + b

    assert isinstance(some_func("1", "2"), str)


def test_arbitrary_args():
    class ArbitraryType:
        def __init__(self):
            self.value = "value"

    @inject
    def some_func(a: ArbitraryType):
        return a

    assert isinstance(some_func(ArbitraryType()), ArbitraryType)


def test_arbitrary_response():
    class ArbitraryType:
        def __init__(self):
            self.value = "value"

    @inject
    def some_func(a: ArbitraryType) -> ArbitraryType:
        return a

    assert isinstance(some_func(ArbitraryType()), ArbitraryType)


def test_args():
    @inject
    def some_func(a, *ar):
        return a, ar

    assert (1, (2,)) == some_func(1, 2)


def test_args_kwargs_1():
    @inject
    def simple_func(
        a: int,
        *args: Tuple[float, ...],
        b: int,
        **kwargs: Dict[str, int],
    ):
        return a, args, b, kwargs

    assert (1, (2.0, 3.0), 3, {"key": 1}) == simple_func(1.0, 2.0, 3, b=3.0, key=1.0)


def test_args_kwargs_2():
    @inject
    def simple_func(
        a: int,
        *args: Tuple[float, ...],
        b: int,
    ):
        return a, args, b

    assert (1, (2.0, 3.0), 3) == simple_func(
        1.0,
        2.0,
        3,
        b=3.0,
    )


def test_args_kwargs_3():
    @inject
    def simple_func(a: int, *, b: int):
        return a, b

    assert (1, 3) == simple_func(
        1.0,
        b=3.0,
    )


def test_args_kwargs_4():
    @inject
    def simple_func(
        *args: Tuple[float, ...],
        **kwargs: Dict[str, int],
    ):
        return args, kwargs

    assert (
        (1.0, 2.0, 3.0),
        {
            "key": 1,
            "b": 3,
        },
    ) == simple_func(1.0, 2.0, 3, b=3.0, key=1.0)


def test_args_kwargs_5():
    @inject
    def simple_func(
        *a: Tuple[float, ...],
        **kw: Dict[str, int],
    ):
        return a, kw

    assert (
        (1.0, 2.0, 3.0),
        {
            "key": 1,
            "b": 3,
        },
    ) == simple_func(1.0, 2.0, 3, b=3.0, key=1.0)


@serializer
class TestSerializer:
    def test_no_cast_result(self):
        @inject(cast_result=False)
        def some_func(a: int, b: int) -> str:
            return a + b

        assert some_func("1", "2") == 3

    def test_annotated_partial(self):
        @inject
        def some_func(a, b: int):
            assert isinstance(b, int)
            return a + b

        assert isinstance(some_func(1, "2"), int)

    def test_types_casting(self):
        @inject
        def some_func(a: int, b: int) -> float:
            assert isinstance(a, int)
            assert isinstance(b, int)
            r = a + b
            assert isinstance(r, int)
            return r

        assert isinstance(some_func("1", "2"), float)

    def test_types_casting_from_str(self):
        @inject
        def some_func(a: "int") -> float:
            return a

        assert isinstance(some_func("1"), float)

    def test_wrong_incoming_types(self):
        @inject
        def some_func(a: int):  # pragma: no cover
            return a

        with pytest.raises(ValidationError):
            some_func({"key", 1})

    def test_wrong_return_type(self):
        @inject
        def some_func(a: int) -> dict:
            return a

        with pytest.raises(ValidationError):
            some_func("2")

    def test_generator(self):
        @inject
        def simple_func(a: str) -> int:
            for _ in range(2):
                yield a

        for i in simple_func("1"):
            assert i == 1

    def test_generator_iterator_type(self):
        @inject
        def simple_func(a: str) -> Iterator[int]:
            for _ in range(2):
                yield a

        for i in simple_func("1"):
            assert i == 1
