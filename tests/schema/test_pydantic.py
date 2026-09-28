from typing import Any

import pytest
from dirty_equals import IsPartialDict

pytest.importorskip("pydantic")

from pydantic import BaseModel, Field, Json

from fast_depends import Depends, inject
from fast_depends.pydantic import PydanticSerializer
from fast_depends.pydantic._compat import PYDANTIC_V2
from tests.marks import pydanticV2


class Node(BaseModel):
    children: list["Node"] = Field(default_factory=list)


def test_bound_schema_preserves_config(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(pydantic_config={"extra": "forbid"}),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(count: int): ...

    assert capture.serializer.get_schema() == IsPartialDict(additionalProperties=False)


def test_bound_schema_preserves_dependency_alias(capture, provider):
    def dependency(count: int = Field(..., alias="size")): ...

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert capture.serializer.get_schema() == IsPartialDict(
        properties={"size": IsPartialDict(type="integer")}, required=["size"]
    )


def test_bound_schema_preserves_dependency_constraints(capture, provider):
    def dependency(count: int = Field(..., gt=0)): ...

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert capture.serializer.get_schema() == IsPartialDict(
        properties={"count": IsPartialDict(exclusiveMinimum=0)}
    )


def test_bound_schema_preserves_default_factory(capture, provider):
    def dependency(values: list[int] = Field(default_factory=list)): ...

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert not capture.serializer.get_schema().get("required")


@pydanticV2
def test_bound_schema_uses_validation_mode(capture, provider):
    def dependency(value: Json[int]): ...

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert capture.serializer.get_schema() == IsPartialDict(
        properties={"value": IsPartialDict(type="string")}
    )


def test_bound_schema_preserves_recursive_references(capture, provider):
    def dependency(node: Node): ...

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    ref_key = "$defs" if PYDANTIC_V2 else "definitions"
    assert capture.serializer.get_schema() == IsPartialDict(
        {
            "properties": {"node": {"$ref": f"#/{ref_key}/Node"}},
            ref_key: {
                "Node": IsPartialDict(
                    properties={
                        "children": IsPartialDict(items={"$ref": f"#/{ref_key}/Node"})
                    }
                )
            },
        }
    )
