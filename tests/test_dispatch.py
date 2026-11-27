import threading
from contextlib import AsyncExitStack
from functools import partial, wraps
from typing import Annotated

import pytest

from fast_depends import Depends, inject, utils
from fast_depends.core import build_call_model, builder, model, preparation
from fast_depends.library import CustomField


@pytest.fixture
def forbid_dispatch_inspection(monkeypatch):
    def forbid():
        def unexpected(*args, **kwargs):
            raise AssertionError("Callable classification belongs to preparation")

        for module in (utils, builder, model, preparation):
            for name in (
                "is_coroutine_callable",
                "is_gen_callable",
                "is_async_gen_callable",
            ):
                if hasattr(module, name):
                    monkeypatch.setattr(module, name, unexpected)

    return forbid


@pytest.mark.anyio
async def test_async_dispatch_preserves_execution_threads(
    provider, forbid_dispatch_inspection
):
    loop_thread = threading.get_ident()

    def sync_dependency(value: int):
        assert threading.get_ident() != loop_thread
        return value + 1

    async def async_dependency(value: int):
        assert threading.get_ident() == loop_thread
        return value + 2

    class SyncField(CustomField):
        def use(self, **kwargs):
            kwargs[self.param_name] = threading.get_ident()
            return kwargs

    class AsyncField(CustomField):
        async def use(self, **kwargs):
            kwargs[self.param_name] = threading.get_ident()
            return kwargs

    @inject(cast=False, dependency_provider=provider)
    async def handler(
        value: int,
        sync_thread: Annotated[int, SyncField()],
        async_thread: Annotated[int, AsyncField()],
        first=Depends(sync_dependency),
        second=Depends(async_dependency),
    ):
        assert threading.get_ident() == loop_thread
        return first, second, sync_thread, async_thread

    forbid_dispatch_inspection()
    first, second, sync_thread, async_thread = await handler(1)
    assert (first, second) == (2, 3)
    assert sync_thread != loop_thread
    assert async_thread == loop_thread


@pytest.mark.anyio
@pytest.mark.parametrize("contextual", [False, True])
async def test_custom_field_modes_dispatch_is_prepared(
    provider, forbid_dispatch_inspection, contextual
):
    token = object()

    class InPlace(CustomField):
        def __init__(self):
            super().__init__()
            self.field = True

        async def use_field(self, values):
            values[self.param_name] = token

    class Context(CustomField):
        async def resolve(self, context, /, **values):
            values[self.param_name] = context["token"]
            return values

    field = Context() if contextual else InPlace()

    @inject(cast=False, dependency_provider=provider, token=token)
    async def handler(value: Annotated[object, field]):
        return value

    forbid_dispatch_inspection()
    assert await handler() is token


@pytest.mark.anyio
async def test_generator_dispatch_preserves_cleanup(provider, forbid_dispatch_inspection):
    events = []
    loop_thread = threading.get_ident()

    def sync_resource():
        assert threading.get_ident() != loop_thread
        events.append("sync open")
        try:
            yield 1
        finally:
            assert threading.get_ident() != loop_thread
            events.append("sync close")

    async def async_resource():
        events.append("async open")
        try:
            yield 2
        finally:
            events.append("async close")

    @inject(cast=False, dependency_provider=provider)
    async def handler(first=Depends(sync_resource), second=Depends(async_resource)):
        events.append("handler")
        return first + second

    forbid_dispatch_inspection()
    assert await handler() == 3
    assert events == ["sync open", "async open", "handler", "async close", "sync close"]


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["instance", "partial", "decorated"])
async def test_prepared_callable_dependencies(provider, forbid_dispatch_inspection, kind):
    async def original(value: int, offset: int = 1):
        return value + offset

    class Dependency:
        async def __call__(self, value: int):
            return await original(value)

    @wraps(original)
    async def decorated(*args, **kwargs):
        return await original(*args, **kwargs)

    dependency = {
        "instance": Dependency(),
        "partial": partial(original, offset=1),
        "decorated": decorated,
    }[kind]

    @inject(cast=False, dependency_provider=provider)
    async def handler(value: int, result=Depends(dependency)):
        return result

    forbid_dispatch_inspection()
    assert await handler(1) == 2


@pytest.mark.anyio
async def test_async_generator_handler_dispatch(provider, forbid_dispatch_inspection):
    @inject(cast=False, dependency_provider=provider)
    async def handler(value: int):
        yield value

    forbid_dispatch_inspection()
    assert [value async for value in handler(1)] == [1]


@pytest.mark.anyio
async def test_wrap_model_prepares_replacement_dispatch(
    provider, forbid_dispatch_inspection
):
    loop_thread = threading.get_ident()

    def replacement(value: int):
        assert threading.get_ident() != loop_thread
        return value + 1

    def replace(call_model):
        call_model.call = replacement
        return call_model

    @inject(cast=False, dependency_provider=provider, wrap_model=replace)
    async def handler(value: int):
        raise AssertionError("The original handler must not execute")

    forbid_dispatch_inspection()
    assert await handler(1) == 2


@pytest.mark.anyio
async def test_sync_handler_supports_explicit_async_mode(
    provider, forbid_dispatch_inspection
):
    loop_thread = threading.get_ident()

    async def dependency(value: int):
        assert threading.get_ident() == loop_thread
        return value + 1

    def handler(value: int, result=Depends(dependency)):
        assert threading.get_ident() != loop_thread
        return value + result

    call_model = build_call_model(handler, dependency_provider=provider, is_sync=False)
    forbid_dispatch_inspection()
    async with AsyncExitStack() as stack:
        assert await call_model.asolve(stack=stack, cache_dependencies={}, value=1) == 3


@pytest.mark.anyio
async def test_prepared_sync_handler_accepts_func_input(
    provider, forbid_dispatch_inspection
):
    def handler(*, func: int):
        return func

    call_model = build_call_model(handler, dependency_provider=provider)
    forbid_dispatch_inspection()
    async with AsyncExitStack() as stack:
        assert await call_model.asolve(stack=stack, cache_dependencies={}, func=1) == 1


@pytest.mark.anyio
async def test_sync_dependency_can_be_shared_with_async_graph(provider):
    def dependency(value: int):
        return value + 1

    @inject(cast=False, dependency_provider=provider)
    def sync_handler(result=Depends(dependency)):
        return result

    @inject(cast=False, dependency_provider=provider)
    async def async_handler(result=Depends(dependency)):
        return result

    assert sync_handler(value=1) == 2
    assert await async_handler(value=1) == 2
