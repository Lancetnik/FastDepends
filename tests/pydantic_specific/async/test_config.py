import pytest

from fast_depends import Depends, Provider, inject
from fast_depends.exceptions import ValidationError
from fast_depends.pydantic import PydanticSerializer


async def dep(a: str):
    return a


@inject(
    serializer_cls=PydanticSerializer(
        {"str_max_length": 1},
        use_fastdepends_errors=True,
    ),
    dependency_provider=Provider(),
)
async def limited_str(a=Depends(dep)): ...


@inject(dependency_provider=Provider())
async def regular(a=Depends(dep)):
    return a


@pytest.mark.anyio
async def test_config() -> None:
    await regular("123")

    with pytest.raises(ValidationError):
        await limited_str("123")
