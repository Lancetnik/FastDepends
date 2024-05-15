import pytest

from fast_depends import Depends, inject
from tests.marks import PYDANTIC_V2, pydantic


async def dep(a: str):
    return a


@inject(pydantic_config={"str_max_length" if PYDANTIC_V2 else "max_anystr_length": 1})
async def limited_str(a=Depends(dep)):
    ...


@inject()
async def regular(a=Depends(dep)):
    return a


@pydantic
@pytest.mark.anyio
async def test_config():
    from pydantic import ValidationError

    await regular("123")

    with pytest.raises(ValidationError):
        await limited_str("123")
