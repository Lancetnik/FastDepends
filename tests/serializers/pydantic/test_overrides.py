from typing import Annotated

import pytest
from pydantic import Field

from fast_depends import Depends, Provider, inject
from fast_depends.pydantic import PydanticSerializer


def dep(a: Annotated[int, Field()] = 1) -> int:
    return a


def dep2(a: Annotated[int, Field()] = 2) -> int:
    return a


@pytest.mark.parametrize(
    "fastdepends_error",
    [
        pytest.param(
            False,
            id="Disabled Fastepends Error",
        ),
        pytest.param(
            True,
            id="Enabled Fastepends Error",
        ),
    ],
)
def test_overrides_after_root_func_creation(
    provider: Provider, fastdepends_error: bool
) -> None:
    @inject(
        serializer_cls=PydanticSerializer(use_fastdepends_errors=fastdepends_error),
        dependency_provider=provider,
    )
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
