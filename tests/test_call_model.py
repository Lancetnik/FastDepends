from contextlib import AsyncExitStack, ExitStack
from unittest.mock import Mock

import pytest

from fast_depends import Depends
from fast_depends.core import build_call_model


def test_recursive_dependency_signature_is_rejected(provider):
    def dependency(value):
        raise AssertionError("Recursive dependencies must not execute")

    dependency.__defaults__ = (Depends(dependency),)
    with pytest.raises(ValueError, match="Dependency cycle involving dependency"):
        build_call_model(dependency, dependency_provider=provider)


def test_plain_root_result_is_reused_from_invocation_cache(provider):
    called = Mock()

    def handler(value: int):
        called()
        return value

    model = build_call_model(handler, dependency_provider=provider)
    cache = {}
    with ExitStack() as stack:
        first = model.solve(stack=stack, cache_dependencies=cache, value=1)
        second = model.solve(stack=stack, cache_dependencies=cache, value=2)
    assert (first, second, called.call_count) == (1, 1, 1)


@pytest.mark.anyio
async def test_plain_async_root_result_is_reused_from_invocation_cache(provider):
    called = Mock()

    async def handler(value: int):
        called()
        return value

    model = build_call_model(handler, dependency_provider=provider)
    cache = {}
    async with AsyncExitStack() as stack:
        first = await model.asolve(stack=stack, cache_dependencies=cache, value=1)
        second = await model.asolve(stack=stack, cache_dependencies=cache, value=2)
    assert (first, second, called.call_count) == (1, 1, 1)
