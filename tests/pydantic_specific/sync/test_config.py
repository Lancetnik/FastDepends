import pytest

from fast_depends import Depends, Provider, inject
from fast_depends.exceptions import ValidationError
from fast_depends.pydantic import PydanticSerializer


def dep(a: str):
    return a


@inject(
    serializer_cls=PydanticSerializer(
        {"str_max_length": 1},
        use_fastdepends_errors=True,
    ),
    dependency_provider=Provider(),
)
def limited_str(a=Depends(dep)): ...


@inject(dependency_provider=Provider())
def regular(a=Depends(dep)):
    return a


def test_config():
    regular("123")

    with pytest.raises(ValidationError):
        limited_str("123")
