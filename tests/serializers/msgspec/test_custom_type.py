from typing import Any, TypeVar

import pytest

from fast_depends import Depends, Provider, inject
from fast_depends.exceptions import ValidationError
from fast_depends.msgspec import MsgSpecSerializer

T = TypeVar("T")


class CustomType:
    def __init__(self, value):
        self.value = value


def msgspec_custom_type_decoder(t: type[T], obj: Any) -> T:
    if not isinstance(obj, t):
        return t(obj)
    return obj


def dep(a: CustomType) -> str:
    return a.value


@inject(
    serializer_cls=MsgSpecSerializer(use_fastdepends_errors=True),
    dependency_provider=Provider(),
)
def custom_type_without_decoder(a: CustomType = Depends(dep)): ...


@inject(
    serializer_cls=MsgSpecSerializer(
        use_fastdepends_errors=True,
        dec_hook=msgspec_custom_type_decoder,
    ),
    dependency_provider=Provider(),
)
def custom_type_with_decoder(a: CustomType = Depends(dep)) -> str:
    assert isinstance(a, CustomType)
    return a.value


def test_custom_type_cast():
    custom_type_with_decoder("123")

    with pytest.raises(ValidationError):
        custom_type_without_decoder("123")
