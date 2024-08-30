import pytest

from fast_depends import Depends, inject
from fast_depends.exceptions import ValidationError
from fast_depends.pydantic import PydanticSerializer
from tests.marks import PYDANTIC_V2


def dep(a: str):
    return a


@inject(
    serializer_cls=PydanticSerializer(
        {"str_max_length" if PYDANTIC_V2 else "max_anystr_length": 1}
    )
)
def limited_str(a=Depends(dep)): ...


@inject()
def regular(a=Depends(dep)):
    return a


def test_config():
    regular("123")

    with pytest.raises(ValidationError):
        limited_str("123")
