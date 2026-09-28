from typing import Annotated

from dirty_equals import IsPartialDict
from pydantic import BaseModel, Field

from fast_depends import Provider
from fast_depends.core import build_call_model
from fast_depends.pydantic._compat import PYDANTIC_V2
from fast_depends.pydantic.schema import get_schema
from tests.schema.custom_fields import Input


class Recursive(BaseModel):
    children: list["Recursive"] = Field(default_factory=list)


def test_legacy_schema_without_runtime_serializer():
    def handler(value: int): ...

    call = build_call_model(handler, dependency_provider=Provider(), serializer_cls=None)

    assert get_schema(call, embed=True) == IsPartialDict(type="integer")


def test_legacy_schema_still_hides_custom_fields():
    def handler(value: Annotated[int, Input("query")]): ...

    call = build_call_model(handler, dependency_provider=Provider(), serializer_cls=None)

    assert get_schema(call) == {"title": "Undefined", "type": "null"}


def test_legacy_resolve_keeps_recursive_definition():
    def handler(value: Recursive): ...

    call = build_call_model(handler, dependency_provider=Provider(), serializer_cls=None)
    schema = get_schema(call, embed=True, resolve_refs=True)
    key = "$defs" if PYDANTIC_V2 else "definitions"

    assert schema[key]["Recursive"]["properties"]["children"]["items"] == {
        "$ref": f"#/{key}/Recursive"
    }


def test_legacy_embed_keeps_definition_without_resolution():
    def handler(value: Recursive): ...

    call = build_call_model(handler, dependency_provider=Provider(), serializer_cls=None)
    schema = get_schema(call, embed=True)
    key = "$defs" if PYDANTIC_V2 else "definitions"

    assert schema["$ref"] == f"#/{key}/Recursive" and "Recursive" in schema[key]
