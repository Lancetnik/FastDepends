import pytest
from pydantic import BaseModel, Field, ValidationError
from typing_extensions import Annotated

from fast_depends import inject


def test_not_annotated():
    @inject
    def some_func(a, b):
        return a + b

    assert isinstance(some_func("1", "2"), str)


def test_annotated_partial():
    @inject
    def some_func(a, b: int):
        assert isinstance(b, int)
        return a + b

    assert isinstance(some_func(1, "2"), int)


def test_validation_error():
    @inject
    def some_func(a, b: str = Field(..., max_length=1)):  # pragma: no cover
        pass

    with pytest.raises(ValidationError):
        assert some_func()

    with pytest.raises(ValidationError):
        assert some_func(1, "dsdas")


def test_types_casting():
    @inject
    def some_func(a: int, b: int) -> float:
        assert isinstance(a, int)
        assert isinstance(b, int)
        r = a + b
        assert isinstance(r, int)
        return r

    assert isinstance(some_func("1", "2"), float)


def test_types_casting_from_str():
    @inject
    def some_func(a: "int") -> float:
        return a

    assert isinstance(some_func("1"), float)


def test_pydantic_types_casting():
    class SomeModel(BaseModel):
        field: int

    @inject
    def some_func(a: SomeModel):
        return a.field

    assert isinstance(some_func({"field": "31"}), int)


def test_pydantic_field_types_casting():
    @inject
    def some_func(a: int = Field(..., alias="b")) -> float:
        assert isinstance(a, int)
        return a

    @inject
    def another_func(a=Field(..., alias="b")) -> float:
        assert isinstance(a, str)
        return a

    assert isinstance(some_func(b="2"), float)
    assert isinstance(another_func(b="2"), float)


def test_wrong_incoming_types():
    @inject
    def some_func(a: int):  # pragma: no cover
        return a

    with pytest.raises(ValidationError):
        some_func({"key", 1})


def test_wrong_return_types():
    @inject
    def some_func(a: int) -> dict:
        return a

    with pytest.raises(ValidationError):
        some_func("2")


def test_annotated():
    A = Annotated[int, Field(..., alias="b")]

    @inject
    def some_func(a: A) -> float:
        assert isinstance(a, int)
        return a

    assert isinstance(some_func(b="2"), float)
