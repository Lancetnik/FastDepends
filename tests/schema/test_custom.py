import inspect
from typing import Annotated, Any
from unittest.mock import Mock

import pytest
from dirty_equals import IsPartialDict

from fast_depends import Depends, inject
from fast_depends.library import CustomField, SchemaField
from tests.schema.custom_fields import Input, source_schema
from tests.serializers.test_schema import resolve_root


def test_custom_field_at_root(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input()]): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"value": IsPartialDict(type="integer")}, required=["value"]
    )


def test_custom_field_default_marker(schema_inject, capture):
    @schema_inject
    def handler(value: int = Input()): ...  # noqa: B008

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"value": IsPartialDict(type="integer")}, required=["value"]
    )


def test_custom_field_default_value(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input()] = 10): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"value": IsPartialDict(default=10)}
    )


def test_custom_field_default_is_optional(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input()] = 10): ...

    assert not resolve_root(capture.serializer.get_schema()).get("required")


def test_uncast_custom_field_preserves_type(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input(cast=False)]): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"value": IsPartialDict(type="integer")}
    )


def test_optional_custom_field_preserves_declared_type(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input(required=False)]): ...

    assert resolve_root(capture.serializer.get_schema())["properties"]["value"] == (
        IsPartialDict(type="integer") & ~IsPartialDict(default=None)
    )


def test_optional_custom_field_is_not_required(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input(required=False)]): ...

    assert not resolve_root(capture.serializer.get_schema()).get("required")


def test_hook_can_override_requiredness(schema_inject, capture):
    class Required(Input):
        def get_schema(self, parameter):
            result = super().get_schema(parameter)
            result.required = True
            return result

    @schema_inject
    def handler(value: Annotated[int, Required(required=False)]): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        required=["value"]
    )


def test_hook_can_hide_input(schema_inject, capture):
    class Hidden(Input):
        def get_schema(self, parameter):
            return None

    @schema_inject
    def handler(value: Annotated[int, Hidden()]): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(properties={})


def test_hook_can_replace_external_name_and_type(schema_inject, capture):
    class Token(CustomField):
        def get_schema(self, parameter):
            return SchemaField("token", str, source="headers")

    @schema_inject
    def handler(value: Annotated[int, Token()]): ...

    assert source_schema(capture.serializer.get_schema(), "headers") == IsPartialDict(
        properties={"token": IsPartialDict(type="string")}, required=["token"]
    )


def test_same_name_in_different_sources(schema_inject, capture):
    def query(value: Annotated[str, Input("query")]): ...

    def path(value: Annotated[float, Input("path")]): ...

    @schema_inject
    def handler(
        value: Annotated[int, Input("headers")],
        q: Any = Depends(query),
        p: Any = Depends(path),
    ): ...

    schema = capture.serializer.get_schema()

    assert {s: source_schema(schema, s) for s in ("headers", "query", "path")} == {
        "headers": IsPartialDict(properties={"value": IsPartialDict(type="integer")}),
        "query": IsPartialDict(properties={"value": IsPartialDict(type="string")}),
        "path": IsPartialDict(properties={"value": IsPartialDict(type="number")}),
    }


def test_arbitrary_source_name(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[str, Input("_custom/source~name")]): ...

    assert source_schema(capture.serializer.get_schema(), "_custom/source~name") == (
        IsPartialDict(properties={"value": IsPartialDict(type="string")})
    )


def test_source_is_required_when_it_has_required_fields(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input("headers")]): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        required=["headers"]
    )


def test_source_with_only_optional_fields_can_be_omitted(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input("headers", required=False)]): ...

    assert not resolve_root(capture.serializer.get_schema()).get("required")


def test_source_required_fields_exclude_optional_fields(schema_inject, capture):
    @schema_inject
    def handler(
        token: Annotated[str, Input("headers")],
        limit: Annotated[int, Input("headers", required=False)],
    ): ...

    assert source_schema(capture.serializer.get_schema(), "headers") == IsPartialDict(
        required=["token"]
    )


def test_duplicate_custom_field_names_fail(schema_inject, capture):
    @schema_inject
    def handler(
        first: Annotated[int, Input("headers", name="value")],
        second: Annotated[str, Input("headers", name="value")],
    ): ...

    with pytest.raises(ValueError, match="Duplicate schema field 'value'.*headers"):
        capture.serializer.get_schema()


def test_custom_field_conflicting_with_plain_input_fails(schema_inject, capture):
    @schema_inject
    def handler(value: int, custom: Annotated[str, Input(name="value")]): ...

    with pytest.raises(ValueError, match="Duplicate schema field 'value'"):
        capture.serializer.get_schema()


def test_source_conflicting_with_root_field_fails(schema_inject, capture):
    @schema_inject
    def handler(headers: int, value: Annotated[str, Input("headers")]): ...

    with pytest.raises(ValueError, match="[Cc]onflict|[Mm]ultiple|[Dd]uplicate"):
        capture.serializer.get_schema()


def test_nested_dependency_custom_field(schema_inject, capture):
    def nested(token: Annotated[str, Input("headers")]): ...

    def dependency(value: Any = Depends(nested)): ...

    @schema_inject
    def handler(value: Any = Depends(dependency)): ...

    assert source_schema(capture.serializer.get_schema(), "headers") == IsPartialDict(
        properties={"token": IsPartialDict(type="string")}
    )


def test_extra_dependency_custom_field(schema_inject, capture):
    def dependency(token: Annotated[str, Input("headers")]): ...

    @schema_inject(extra_dependencies=(Depends(dependency),))
    def handler(): ...

    assert source_schema(capture.serializer.get_schema(), "headers") == IsPartialDict(
        properties={"token": IsPartialDict(type="string")}
    )


def test_shared_dependency_is_described_once(schema_inject, capture):
    def dependency(token: Annotated[str, Input("headers")]): ...

    @schema_inject(extra_dependencies=(Depends(dependency),))
    def handler(first: Any = Depends(dependency), second: Any = Depends(dependency)): ...

    assert source_schema(capture.serializer.get_schema(), "headers") == IsPartialDict(
        properties={"token": IsPartialDict(type="string")}
    )


def test_custom_field_override_after_schema(schema_inject, capture, provider):
    def original(value: Annotated[int, Input("headers")]): ...

    def replacement(value: Annotated[str, Input("query")]): ...

    @schema_inject
    def handler(value: Any = Depends(original)): ...

    capture.serializer.get_schema()
    provider.override(original, replacement)

    assert list(resolve_root(capture.serializer.get_schema())["properties"]) == ["query"]


def test_extra_custom_field_override_before_decoration(schema_inject, capture, provider):
    def original(value: Annotated[int, Input("headers")]): ...

    def replacement(value: Annotated[str, Input("query", cast=False)]): ...

    provider.override(original, replacement)

    @schema_inject(extra_dependencies=(Depends(original),))
    def handler(): ...

    assert source_schema(capture.serializer.get_schema(), "query") == IsPartialDict(
        properties={"value": IsPartialDict(type="string")}
    )


def test_custom_field_inside_provider_scope(schema_inject, capture, provider):
    def original(value: Annotated[int, Input("headers")]): ...

    def replacement(value: Annotated[str, Input("query")]): ...

    @schema_inject
    def handler(value: Any = Depends(original)): ...

    with provider.scope(original, replacement):
        assert list(resolve_root(capture.serializer.get_schema())["properties"]) == [
            "query"
        ]


def test_custom_field_after_provider_scope(schema_inject, capture, provider):
    def original(value: Annotated[int, Input("headers")]): ...

    def replacement(value: Annotated[str, Input("query")]): ...

    @schema_inject
    def handler(value: Any = Depends(original)): ...

    with provider.scope(original, replacement):
        capture.serializer.get_schema()

    assert list(resolve_root(capture.serializer.get_schema())["properties"]) == [
        "headers"
    ]


def test_hook_receives_original_parameter(schema_inject, capture):
    received = []

    class Capture(CustomField):
        def get_schema(self, parameter):
            received.append(
                (
                    parameter.field_name,
                    parameter.field_type,
                    parameter.default_value,
                    parameter.kind,
                )
            )

    @schema_inject
    def handler(*, value: Annotated[int, Capture(cast=False, required=False)] = 10): ...

    capture.serializer.get_schema()

    assert received == [("value", int, 10, inspect.Parameter.KEYWORD_ONLY)]


def test_schema_does_not_execute_custom_methods(schema_inject, capture):
    class Described(Input):
        def use(self, **kwargs):
            raise AssertionError("use executed")

        def use_field(self, kwargs):
            raise AssertionError("use_field executed")

    @schema_inject
    def handler(value: Annotated[int, Described("headers")]): ...

    assert source_schema(capture.serializer.get_schema(), "headers") == IsPartialDict(
        properties={"value": IsPartialDict(type="integer")}
    )


def test_schema_preserves_custom_casting(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input("headers")]):
        return value

    capture.serializer.get_schema()

    assert handler(headers={"value": "12"}) == 12


def test_schema_preserves_disabled_custom_casting(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input("headers", cast=False)]):
        return value

    capture.serializer.get_schema()

    assert handler(headers={"value": "12"}) == "12"


@pytest.mark.anyio
async def test_schema_preserves_async_custom_execution(schema_inject, capture):
    class AsyncInput(Input):
        async def use(self, **kwargs):
            return super().use(**kwargs)

    @schema_inject
    async def handler(value: Annotated[int, AsyncInput("headers")]) -> str:
        return str(value)

    capture.serializer.get_schema()

    assert await handler(headers={"value": "12"}) == "12"


def test_custom_schema_does_not_create_serializer(serializer_factory, capture, provider):
    factory = Mock(wraps=serializer_factory)

    @inject(serializer_cls=factory, dependency_provider=provider, wrap_model=capture)
    def handler(value: Annotated[int, Input("headers")]): ...

    factory.reset_mock()
    capture.serializer.get_schema()

    factory.assert_not_called()


def test_custom_hook_is_lazy(schema_inject):
    class Lazy(Input):
        def get_schema(self, parameter):
            raise AssertionError("Schema hook executed outside get_schema()")

    @schema_inject
    def handler(value: Annotated[int, Lazy("headers")]):
        return value

    assert handler(headers={"value": "12"}) == 12


def test_custom_hook_can_remove_requiredness(schema_inject, capture):
    class OptionalInput(Input):
        def get_schema(self, parameter):
            result = super().get_schema(parameter)
            result.required = False
            return result

    @schema_inject
    def handler(value: Annotated[int, OptionalInput()]): ...

    assert not resolve_root(capture.serializer.get_schema()).get("required")


def test_hook_receives_fresh_parameter_description(schema_inject, capture):
    class Renamed(Input):
        def get_schema(self, parameter):
            parameter.field_name += "_input"
            return super().get_schema(parameter)

    @schema_inject
    def handler(value: Annotated[int, Renamed()]): ...

    capture.serializer.get_schema()

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"value_input": IsPartialDict(type="integer")}
    )


def test_empty_source_fails(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input("")]): ...

    with pytest.raises(ValueError, match="source must be a non-empty string"):
        capture.serializer.get_schema()


def test_invalid_hook_result_fails(schema_inject, capture):
    class Invalid(Input):
        def get_schema(self, parameter):
            return {"type": "integer"}

    @schema_inject
    def handler(value: Annotated[int, Invalid()]): ...

    with pytest.raises(TypeError, match="must return SchemaField or None"):
        capture.serializer.get_schema()
