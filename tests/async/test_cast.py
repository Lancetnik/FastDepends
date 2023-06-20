import pytest
from pydantic import BaseModel, Field, ValidationError
from typing_extensions import Annotated

from fast_depends import inject


@pytest.mark.asyncio
async def test_not_annotated():
    @inject
    async def some_func(a, b):
        return a + b

    assert isinstance(await some_func("1", "2"), str)


@pytest.mark.asyncio
async def test_annotated_partial():
    @inject
    async def some_func(a, b: int):
        assert isinstance(b, int)
        return a + b

    assert isinstance(await some_func(1, "2"), int)


@pytest.mark.asyncio
async def test_types_casting():
    @inject
    async def some_func(a: int, b: int) -> float:
        assert isinstance(a, int)
        assert isinstance(b, int)
        r = a + b
        assert isinstance(r, int)
        return r

    assert isinstance(await some_func("1", "2"), float)


@pytest.mark.asyncio
async def test_types_casting_from_str():
    @inject
    async def some_func(a: "int") -> float:
        return a

    assert isinstance(await some_func("1"), float)


@pytest.mark.asyncio
async def test_pydantic_types_casting():
    class SomeModel(BaseModel):
        field: int

    @inject
    async def some_func(a: SomeModel):
        return a.field

    assert isinstance(await some_func({"field": "31"}), int)


@pytest.mark.asyncio
async def test_pydantic_field_types_casting():
    @inject
    async def some_func(a: int = Field(..., alias="b")) -> float:
        assert isinstance(a, int)
        return a

    @inject
    async def another_func(a=Field(..., alias="b")) -> float:
        assert isinstance(a, str)
        return a

    assert isinstance(await some_func(b="2", c=3), float)
    assert isinstance(await another_func(b="2"), float)


@pytest.mark.asyncio
async def test_wrong_incoming_types():
    @inject
    async def some_func(a: int):  # pragma: no cover
        return a

    with pytest.raises(ValidationError):
        await some_func({"key", 1})


@pytest.mark.asyncio
async def test_wrong_return_types():
    @inject
    async def some_func(a: int) -> dict:
        return a

    with pytest.raises(ValidationError):
        await some_func("2")


@pytest.mark.asyncio
async def test_annotated():
    A = Annotated[int, Field(..., alias="b")]

    @inject
    async def some_func(a: A) -> float:
        assert isinstance(a, int)
        return a

    assert isinstance(await some_func(b="2"), float)
