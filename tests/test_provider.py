from contextlib import AsyncExitStack, ExitStack

import pytest

from fast_depends import Depends, Provider
from fast_depends.core import build_call_model


def base_dep() -> int:
    return 1


def override_dep() -> int:
    return 2


def sync_func(d: int = Depends(base_dep)) -> int:
    return d


async def async_func(d: int = Depends(base_dep)) -> int:
    return d


def call_level_provider() -> Provider:
    provider = Provider()
    provider.override(base_dep, override_dep)
    return provider


def test_merge_keeps_both_sides() -> None:
    original, extra = Provider(), call_level_provider()
    original.add_dependant(build_call_model(sync_func, dependency_provider=original))

    merged = original.merge(extra)

    assert merged is not original
    assert merged is not extra
    assert merged.dependencies == original.dependencies | extra.dependencies
    assert merged.overrides == original.overrides | extra.overrides
    # merging must not mutate either side
    assert not original.overrides


def test_sync_call_level_provider() -> None:
    provider = Provider()
    model = build_call_model(sync_func, dependency_provider=provider)

    with ExitStack() as stack:
        assert model.solve(stack=stack, cache_dependencies={}) == 1

    with ExitStack() as stack:
        assert (
            model.solve(
                stack=stack,
                cache_dependencies={},
                dependency_provider=call_level_provider(),
            )
            == 2
        )

    # the call-level provider must not leak into the model's own provider
    with ExitStack() as stack:
        assert model.solve(stack=stack, cache_dependencies={}) == 1


@pytest.mark.anyio
async def test_async_call_level_provider() -> None:
    provider = Provider()
    model = build_call_model(async_func, dependency_provider=provider)

    async with AsyncExitStack() as stack:
        assert await model.asolve(stack=stack, cache_dependencies={}) == 1

    async with AsyncExitStack() as stack:
        assert (
            await model.asolve(
                stack=stack,
                cache_dependencies={},
                dependency_provider=call_level_provider(),
            )
            == 2
        )

    async with AsyncExitStack() as stack:
        assert await model.asolve(stack=stack, cache_dependencies={}) == 1
