from typing import Annotated

from pydantic import Field

from fast_depends import Depends, Provider, inject
from fast_depends.pydantic import PydanticSerializer


def dep(a: Annotated[int, Field(default=1)]) -> int:
    return a


def dep2(a: Annotated[int, Field(default=2)]) -> int:
    return a


def test_overrides_after_root_func_creation(provider: Provider) -> None:
    @inject(serializer_cls=PydanticSerializer(), dependency_provider=provider)
    def func(a: Annotated[int, Depends(dep)]) -> int:
        return a

    assert func() == 1
    with provider.scope(dep, dep2):
        assert func() == 2


def test_overrides_before_root_func_creation(provider: Provider) -> None:
    provider.override(dep, dep2)

    @inject(serializer_cls=PydanticSerializer(), dependency_provider=provider)
    def func(a: Annotated[int, Depends(dep)]) -> int:
        return a

    assert func() == 2
