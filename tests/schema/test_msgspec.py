from typing import Annotated, Any

import pytest
from dirty_equals import IsPartialDict

pytest.importorskip("msgspec")

import msgspec

from fast_depends import Depends, inject
from fast_depends.msgspec import MsgSpecSerializer
from tests.serializers.test_schema import resolve_root


class Node(msgspec.Struct):
    children: list["Node"] = msgspec.field(default_factory=list)


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
