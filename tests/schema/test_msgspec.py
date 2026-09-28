from typing import Annotated, Any

import pytest
from dirty_equals import IsPartialDict

pytest.importorskip("msgspec")

import msgspec

from fast_depends import Depends, inject
from fast_depends.msgspec import MsgSpecSerializer
from tests.schema.custom_fields import Input, source_schema
from tests.serializers.test_schema import resolve_root


class Node(msgspec.Struct):
    children: "list[Node]" = msgspec.field(default_factory=list)


def test_bound_schema_preserves_dependency_alias(capture, provider):
    def dependency(count: int = msgspec.field(name="size")): ...

    @inject(
        serializer_cls=MsgSpecSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"size": IsPartialDict(type="integer")}, required=["size"]
    )


def test_bound_schema_preserves_dependency_constraints(capture, provider):
    def dependency(count: Annotated[int, msgspec.Meta(gt=0)]): ...

    @inject(
        serializer_cls=MsgSpecSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"count": IsPartialDict(exclusiveMinimum=0)}
    )


def test_bound_schema_preserves_default_factory(capture, provider):
    default = msgspec.field(default_factory=list)

    def dependency(values: list[int] = default): ...

    @inject(
        serializer_cls=MsgSpecSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert not resolve_root(capture.serializer.get_schema()).get("required")


def test_bound_schema_preserves_recursive_references(capture, provider):
    def dependency(node: Node): ...

    @inject(
        serializer_cls=MsgSpecSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert capture.serializer.get_schema() == IsPartialDict(
        {
            "$ref": "#/$defs/handler",
            "$defs": {
                "handler": IsPartialDict(properties={"node": {"$ref": "#/$defs/Node"}}),
                "Node": IsPartialDict(
                    properties={"children": IsPartialDict(items={"$ref": "#/$defs/Node"})}
                ),
            },
        }
    )


def test_custom_field_preserves_alias(capture, provider):
    @inject(
        serializer_cls=MsgSpecSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        value: Annotated[int, Input("headers")] = msgspec.field(name="x-value"),
    ): ...

    assert source_schema(capture.serializer.get_schema(), "headers") == IsPartialDict(
        properties={"x-value": IsPartialDict(type="integer")}, required=["x-value"]
    )


def test_uncast_custom_field_preserves_annotated_constraints(capture, provider):
    @inject(
        serializer_cls=MsgSpecSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        value: Annotated[int, Input("query", cast=False), msgspec.Meta(gt=0)],
    ): ...

    assert source_schema(capture.serializer.get_schema(), "query") == IsPartialDict(
        properties={"value": IsPartialDict(type="integer", exclusiveMinimum=0)}
    )


def test_custom_field_preserves_default_factory(capture, provider):
    default = msgspec.field(default_factory=list)

    @inject(
        serializer_cls=MsgSpecSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        values: Annotated[list[int], Input("query")] = default,
    ): ...

    assert not source_schema(capture.serializer.get_schema(), "query").get("required")


def test_custom_field_alias_collision_fails(capture, provider):
    class AliasedInput(Input):
        def get_schema(self, parameter):
            description = super().get_schema(parameter)
            description.default_value = msgspec.field(name="value")
            return description

    @inject(
        serializer_cls=MsgSpecSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        first: Annotated[int, AliasedInput("headers")],
        second: Annotated[str, AliasedInput("headers")],
    ): ...

    with pytest.raises(ValueError, match="Multiple fields rename to the same name"):
        capture.serializer.get_schema()


def test_custom_field_preserves_recursive_references(capture, provider):
    @inject(
        serializer_cls=MsgSpecSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(node: Annotated[Node, Input("query")]): ...

    schema = capture.serializer.get_schema()

    assert {"group": source_schema(schema, "query"), "node": schema["$defs"]["Node"]} == {
        "group": IsPartialDict(properties={"node": {"$ref": "#/$defs/Node"}}),
        "node": IsPartialDict(
            properties={"children": IsPartialDict(items={"$ref": "#/$defs/Node"})}
        ),
    }
