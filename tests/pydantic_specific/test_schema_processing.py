from typing import Annotated

import pytest
from dirty_equals import IsPartialDict
from pydantic import BaseModel, Field

from fast_depends import Provider
from fast_depends.core import build_call_model
from fast_depends.pydantic import PydanticSerializer
from fast_depends.pydantic.schema import get_schema
from tests.schema.custom_fields import Input, source_schema


class Recursive(BaseModel):
    children: list["Recursive"] = Field(default_factory=list)


def test_helper_requires_configured_serializer():
    def handler(value: int): ...

    call = build_call_model(handler, dependency_provider=Provider(), serializer_cls=None)
    with pytest.raises(ValueError, match="configured serializer"):
        get_schema(call, embed=True)


def test_helper_includes_described_custom_fields():
    def handler(value: Annotated[int, Input("query")]): ...

    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=PydanticSerializer()
    )
    schema = get_schema(call)
    assert source_schema(schema, "query") == IsPartialDict(
        properties={"value": IsPartialDict(type="integer")}, required=["value"]
    )
    assert schema == call.serializer.get_schema()


def test_helper_resolve_keeps_recursive_definition():
    def handler(value: Recursive): ...

    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=PydanticSerializer()
    )
    schema = get_schema(call, embed=True, resolve_refs=True)
    assert schema["$defs"]["Recursive"]["properties"]["children"]["items"] == {
        "$ref": "#/$defs/Recursive"
    }
    assert schema == call.serializer.get_schema(embed=True, resolve_refs=True)


def test_helper_embed_keeps_definition_without_resolution():
    def handler(value: Recursive): ...

    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=PydanticSerializer()
    )
    schema = get_schema(call, embed=True)
    assert schema["$ref"] == "#/$defs/Recursive" and "Recursive" in schema["$defs"]


def test_helper_preserves_factory_config():
    def handler(value: int): ...

    factory = PydanticSerializer(
        pydantic_config={"extra": "forbid", "alias_generator": lambda name: f"api_{name}"}
    )
    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=factory
    )
    schema = get_schema(call)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["api_value"]
    assert list(schema["properties"]) == ["api_value"]
    assert schema == call.serializer.get_schema()
