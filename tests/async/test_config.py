import pytest
from pydantic import ValidationError

from fast_depends import Depends, inject
from fast_depends._compat import PYDANTIC_V2


async def dep(a: str):
    return a


@inject(pydantic_config={"str_max_length" if PYDANTIC_V2 else "max_anystr_length": 1})
async def limited_str(a=Depends(dep)):
    return a


@inject()
async def regular(a=Depends(dep)):
    return a


@pytest.mark.anyio
async def test_config():
    await regular("123")

    with pytest.raises(ValidationError):
        await limited_str("123")
