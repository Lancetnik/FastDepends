from collections.abc import Generator
from contextlib import AsyncExitStack, ExitStack
from typing import Annotated, Any
from unittest.mock import Mock

import anyio
import pytest

from fast_depends import Depends, inject
from fast_depends.core import build_call_model
from fast_depends.exceptions import ValidationError
from fast_depends.library import CustomField
from fast_depends.library.serializer import SerializerProto
from tests.serializers.test_schema import resolve_root


@pytest.fixture(
    params=[
        pytest.param("pydantic", id="pydantic"),
        pytest.param("msgspec", id="msgspec"),
    ]
)
def backend(request: pytest.FixtureRequest) -> SerializerProto:
    pytest.importorskip(request.param)
    if request.param == "pydantic":
        from fast_depends.pydantic import PydanticSerializer

        return PydanticSerializer()
    from fast_depends.msgspec import MsgSpecSerializer

    return MsgSpecSerializer()


def _aliased_field(backend):
    if type(backend).__module__.startswith("fast_depends.msgspec"):
        import msgspec

        return msgspec.field(name="external")
    from pydantic import Field

    return Field(alias="external")


def test_converted_mutable_input_is_shared(backend, provider):
    def dependency(items: list[int]):
        items.append(2)
        return items

    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(items: list[int], result=Depends(dependency)):
        return items, result is items

    assert handler(items=["1"]) == ([1, 2], True)


def test_context_only_field_needs_no_external_input(backend, provider):
    token = object()

    class Token(CustomField):
        def resolve(self, context, /, **kwargs):
            kwargs[self.param_name] = context["token"]
            return kwargs

    @inject(serializer_cls=backend, dependency_provider=provider, token=token)
    def handler(value: Annotated[Any, Token()]):
        return value

    assert handler() is token


def test_missing_input_keeps_each_consumer_default(backend, provider):
    def dependency(value: int = 1):
        return value

    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(value: int = 2, result=Depends(dependency)):
        return value, result

    assert handler() == (2, 1)


def test_conflicting_native_constraints_are_rejected(backend, provider):
    if type(backend).__module__.startswith("fast_depends.msgspec"):
        from msgspec import Meta

        Value = Annotated[int, Meta(gt=0)]
    else:
        from annotated_types import Gt

        Value = Annotated[int, Gt(0)]

    def dependency(value: Value): ...

    with pytest.raises(TypeError, match=r"handler\.value.*dependency\.value"):

        @inject(serializer_cls=backend, dependency_provider=provider)
        def handler(value: int, result=Depends(dependency)): ...


@pytest.mark.parametrize(
    "required",
    [
        pytest.param(False, id="consumer-defaults"),
        pytest.param(True, id="required-consumer"),
    ],
)
def test_shared_schema_requiredness_has_no_consumer_default(backend, provider, required):
    def optional_consumer(value: int = 1): ...

    def required_consumer(value: int): ...

    dependency = required_consumer if required else optional_consumer
    serializer = None

    def capture(model):
        nonlocal serializer
        serializer = model.serializer
        return model

    @inject(serializer_cls=backend, dependency_provider=provider, wrap_model=capture)
    def handler(value: int = 2, result=Depends(dependency)): ...

    assert serializer is not None
    schema = resolve_root(serializer.get_schema())
    assert (
        "default" in schema["properties"]["value"],
        "value" in schema.get("required", ()),
    ) == (False, required)


@pytest.mark.parametrize(
    "arguments",
    [pytest.param({}, id="missing"), pytest.param({"value": "invalid"}, id="invalid")],
)
def test_required_shared_input_fails_before_dependencies(backend, provider, arguments):

    def extra():
        raise AssertionError("Dependencies must not execute for invalid inputs")

    def dependency(value: int):
        raise AssertionError("Dependencies must not execute for invalid inputs")

    @inject(
        serializer_cls=backend,
        dependency_provider=provider,
        extra_dependencies=(Depends(extra),),
    )
    def handler(value: int = 2, result=Depends(dependency)): ...

    with pytest.raises(ValidationError):
        handler(**arguments)


def test_different_local_names_share_external_alias(backend, provider):
    def dependency(child: list[int] = _aliased_field(backend)):  # noqa: B008
        return child

    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(parent: list[int] = _aliased_field(backend), result=Depends(dependency)):  # noqa: B008
        return parent is result

    assert handler(external=["1"]) is True


def test_root_parameters_share_one_aliased_value(backend, provider):
    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(
        first: list[int] = _aliased_field(backend),  # noqa: B008
        second: list[int] = _aliased_field(backend),  # noqa: B008
    ):
        return first, first is second

    assert handler(external=["1"]) == ([1], True)


@pytest.mark.parametrize("default_kind", ["required", "value", "factory"])
def test_distinct_aliases_with_one_local_name_keep_both_schema_fields(
    backend, provider, default_kind
):
    def field(alias):
        defaults = (
            {"default": 2}
            if default_kind == "value"
            else {"default_factory": lambda: 2}
            if default_kind == "factory"
            else {}
        )
        if type(backend).__module__.startswith("fast_depends.msgspec"):
            import msgspec

            return msgspec.field(name=alias, **defaults)
        from pydantic import Field

        return Field(alias=alias, **defaults)

    def dependency(value: int = field("right")):  # noqa: B008
        return value

    def handler(value: int = field("left"), value_: int = 0, result=Depends(dependency)):  # noqa: B008
        return value, result

    model = build_call_model(
        handler, serializer_cls=backend, dependency_provider=provider
    )
    schema = resolve_root(model.serializer.get_schema())
    assert set(schema["properties"]) == {"left", "right", "value_"}
    assert schema["properties"]["right"].get("default") == (
        2 if default_kind == "value" else None
    )
    excluded = resolve_root(model.serializer.get_schema(exclude=["value"]))
    assert set(excluded["properties"]) == {"value_"}
    with ExitStack() as stack:
        assert model.solve(stack=stack, cache_dependencies={}, left="1", right="2") == (
            1,
            2,
        )


@pytest.mark.parametrize(
    "cached", [pytest.param(True, id="cached"), pytest.param(False, id="uncached")]
)
def test_custom_replacement_preserves_dependency_cache(backend, provider, cached):
    class Replace(CustomField):
        def use(self, **kwargs):
            kwargs["items"] = [9]
            kwargs[self.param_name] = None
            return kwargs

    def total(items: list[int]):
        return sum(items)

    def replace(changed: Any = Replace()): ...  # noqa: B008

    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(
        before=Depends(total, use_cache=cached),
        changed=Depends(replace),
        after=Depends(total, use_cache=cached),
    ):
        return before, after

    assert handler(items=[1]) == (1, 1 if cached else 9)


@pytest.mark.parametrize(
    "remove,arguments,expected",
    [
        pytest.param(True, {"value": 4}, (2, 4), id="remove"),
        pytest.param(False, {}, (9, 1), id="supply"),
    ],
)
def test_custom_changes_preserve_each_consumers_missing_default(
    backend, provider, remove, arguments, expected
):
    class ChangeInput(CustomField):
        def use(self, **kwargs):
            if remove:
                kwargs.pop("value")
            else:
                kwargs["value"] = 9
            kwargs[self.param_name] = None
            return kwargs

    def dependency(value: int = 1):
        return value

    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(value: int = 2, changed: Any = ChangeInput(), before=Depends(dependency)):  # noqa: B008
        return value, before

    assert handler(**arguments) == expected


def test_solver_option_names_are_ordinary_arguments(backend, provider):
    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(stack: int, context: int, dependency_provider: int):
        return stack + context + dependency_provider

    assert handler(stack="1", context="2", dependency_provider="3") == 6


def test_structural_shared_types_without_serializer(provider):
    def dependency(items: list[int]):
        return items

    @inject(serializer_cls=None, dependency_provider=provider)
    def handler(items: list[int], result=Depends(dependency)):
        return items is result

    with pytest.raises(TypeError, match="Missing required argument"):
        handler()
    assert handler([1]) is True


def test_mixed_dependency_cache_policies(backend, provider):
    called = Mock(side_effect=[1, 2])

    def dependency():
        return called()

    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(
        first=Depends(dependency),
        uncached=Depends(dependency, use_cache=False),
        last=Depends(dependency),
    ):
        return first, uncached, last

    assert handler() == (1, 2, 1)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "async_call", [pytest.param(False, id="sync"), pytest.param(True, id="async")]
)
async def test_framework_context_is_separate_from_body(backend, provider, async_call):
    request = object()

    class Request(CustomField):
        def resolve(self, context, /, **kwargs):
            kwargs = super().resolve(context, **kwargs)
            kwargs[self.param_name] = context["request"]
            return kwargs

    def handler(request: int, context: int, resolved: Any = Request()):  # noqa: B008
        return request, context, resolved

    model = build_call_model(
        handler, dependency_provider=provider, serializer_cls=backend
    )
    options = {
        "cache_dependencies": {},
        "arguments": ((), {"request": "1", "context": "2"}),
        "context": {"request": request},
    }
    if async_call:
        async with AsyncExitStack() as stack:
            result = await model.asolve(stack=stack, **options)
    else:
        with ExitStack() as stack:
            result = model.solve(stack=stack, **options)
    assert result == (1, 2, request)


def test_root_generator_failure_closes_dependency(backend, provider):
    closed = Mock()

    def resource():
        try:
            yield 1
        finally:
            closed()

    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(value: int = Depends(resource)) -> Generator[int, None, None]:
        yield value
        raise ValueError("failed iteration")

    iterator = handler()
    with pytest.raises(ValueError, match="failed iteration"):
        list(iterator)
    closed.assert_called_once()


@pytest.mark.anyio
@pytest.mark.parametrize("async_call", [False, True])
async def test_generator_fields_receive_separate_context(backend, provider, async_call):
    request = object()

    class Request(CustomField):
        def resolve(self, context, /, **kwargs):
            kwargs[self.param_name] = context["request"]
            return kwargs

    def sync_handler(context: int, request: Annotated[Any, Request()]):
        yield context, request

    async def async_handler(context: int, request: Annotated[Any, Request()]):
        yield context, request

    handler = inject(
        async_handler if async_call else sync_handler,
        serializer_cls=backend,
        dependency_provider=provider,
        request=request,
    )
    result = (
        [item async for item in handler(context="1")]
        if async_call
        else list(handler(context="1"))
    )
    assert result == [(1, request)]


@pytest.mark.anyio
async def test_async_call_accepts_positional_only_generator_dependency(backend, provider):
    def resource(value: int, /):
        yield value

    @inject(serializer_cls=backend, dependency_provider=provider)
    async def handler(value: int, result: int = Depends(resource)):
        return result

    assert await handler("1") == 1


@pytest.mark.anyio
async def test_async_root_generator_failure_closes_dependency(backend, provider):
    closed = Mock()

    async def resource():
        try:
            yield 1
        finally:
            closed()

    @inject(serializer_cls=backend, dependency_provider=provider)
    async def handler(value: int = Depends(resource)):
        yield value
        raise ValueError("failed iteration")

    iterator = handler()
    with pytest.raises(ValueError, match="failed iteration"):
        _ = [value async for value in iterator]
    closed.assert_called_once()


def test_positional_only_argument_rejects_keyword(backend, provider):
    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(value: int, /):
        raise AssertionError("Invalid positional binding must not execute")

    with pytest.raises(TypeError, match="Positional-only argument"):
        handler(value=1)


def test_positional_only_name_remains_available_in_extra_keywords(backend, provider):
    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(value: int, /, **extra: dict[str, int]):
        return value, extra

    assert handler("1", value="2") == (1, {"value": 2})


@pytest.mark.parametrize(
    "args,kwargs,error",
    [
        pytest.param((1,), {"value": 2}, "Multiple values", id="duplicate"),
        pytest.param((1, 2), {}, "Too many positional", id="too-many"),
    ],
)
def test_invalid_python_binding_fails_before_execution(provider, args, kwargs, error):
    @inject(serializer_cls=None, dependency_provider=provider)
    def handler(value):
        raise AssertionError("Invalid arguments must not execute the handler")

    with pytest.raises(TypeError, match=error):
        handler(*args, **kwargs)


def test_missing_positional_only_argument_keeps_python_error(provider):
    @inject(serializer_cls=None, dependency_provider=provider)
    def handler(value, /):
        raise AssertionError("Missing arguments must not execute the handler")

    with pytest.raises(TypeError, match="missing 1 required positional argument"):
        handler()


def test_nested_provider_scope_restores_contract(backend, provider):
    def original(value: int):
        return value

    def outer(outer_value: int):
        return outer_value + 10

    def inner(inner_value: int):
        return inner_value + 20

    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(result=Depends(original)):
        return result

    with provider.scope(original, outer):
        first = handler(outer_value=1)
        with provider.scope(original, inner):
            second = handler(inner_value=2)
        third = handler(outer_value=3)
    assert (first, second, third, handler(value=4)) == (11, 22, 13, 4)


def test_provider_override_cannot_introduce_dependency_cycle(backend, provider):
    def leaf():
        raise AssertionError("Cyclic dependencies must not execute")

    def handler(result=Depends(leaf)):
        raise AssertionError("Cyclic dependencies must not execute")

    wrapped = inject(handler, serializer_cls=backend, dependency_provider=provider)
    with pytest.raises(ValueError, match="Dependency cycle"):
        provider.override(leaf, handler)
        wrapped()


def test_async_override_is_rejected_for_sync_handler(backend, provider):
    def dependency():
        raise AssertionError("The original dependency must not execute")

    async def replacement():
        raise AssertionError("An async dependency must not execute from a sync call")

    @inject(serializer_cls=backend, dependency_provider=provider)
    def handler(result=Depends(dependency)):
        raise AssertionError("Invalid dependency graphs must not execute")

    provider.override(dependency, replacement)
    with pytest.raises(TypeError, match="async dependency"):
        handler()


@pytest.mark.anyio
async def test_provider_changes_do_not_replace_inflight_graph(backend, provider):
    started, release = anyio.Event(), anyio.Event()
    results = []

    async def pause():
        started.set()
        await release.wait()

    def original(token: int):
        return token

    def replacement(user_id: int):
        return user_id + 10

    @inject(serializer_cls=backend, dependency_provider=provider)
    async def handler(wait=Depends(pause), result=Depends(original)):
        return result

    async def run():
        results.append(await handler(token=1))

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(run)
        await started.wait()
        provider.override(original, replacement)
        release.set()

    assert (results, await handler(user_id=2)) == ([1], 12)


def test_input_transform_runs_once_before_contextual_validation(provider):
    pytest.importorskip("pydantic")
    from pydantic import AfterValidator, BeforeValidator, ValidationInfo, WrapValidator

    calls = Mock()

    def prepare(value: int) -> int:
        calls()
        return value + 1

    def contextual(value: int, info: ValidationInfo) -> int:
        return value + info.data.get("offset", 0)

    def convert(value):
        return int(value)

    def wrap(value, handler):
        return handler(value)

    Value = Annotated[
        int,
        BeforeValidator(convert),
        WrapValidator(wrap),
        AfterValidator(prepare),
        AfterValidator(contextual),
    ]

    def dependency(value: Value):
        return value

    def offset():
        return 10

    @inject(dependency_provider=provider)
    def handler(
        offset: int = Depends(offset), value: Value = 0, result=Depends(dependency)
    ):
        return value, result

    assert handler(value="1") == (12, 2)
    calls.assert_called_once()


def test_default_factory_reads_resolved_dependency(provider):
    pytest.importorskip("pydantic")
    from pydantic import Field

    def offset():
        return 10

    @inject(dependency_provider=provider)
    def handler(
        offset: int = Depends(offset),
        value: int = Field(default_factory=lambda values: values["offset"] + 1),
    ):
        return value

    assert handler() == 11
