import pytest
from annotated_types import Ge
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from fast_depends import inject
from fast_depends.exceptions import ValidationError
from tests.marks import pydanticV2


@pytest.mark.anyio
async def test_pydantic_types_casting():
    class SomeModel(BaseModel):
        field: int

    @inject
    async def some_func(a: SomeModel):
        return a.field

    assert isinstance(await some_func({"field": "31"}), int)


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_annotated():
    A = Annotated[int, Field(..., alias="b")]

    @inject
    async def some_func(a: A) -> float:
        assert isinstance(a, int)
        return a

    assert isinstance(await some_func(b="2"), float)


@pytest.mark.anyio
async def test_generator():
    @inject
    async def simple_func(a: str) -> int:
        for _ in range(2):
            yield a

    async for i in simple_func("1"):
        assert i == 1


@pytest.mark.anyio
async def test_validation_error():
    @inject
    async def some_func(a, b: str = Field(..., max_length=1)):
        return 1

    assert await some_func(1, "a") == 1

    with pytest.raises(ValidationError):
        assert await some_func()

    with pytest.raises(ValidationError):
        assert await some_func(1, "dsdas")


@pytest.mark.anyio
@pydanticV2
async def test_multi_annotated():
    from pydantic.functional_validators import AfterValidator

    @inject()
    async def f(a: Annotated[int, Ge(10), AfterValidator(lambda x: x + 10)]) -> int:
        return a

    with pytest.raises(ValidationError):
        await f(1)

    assert await f(10) == 20
