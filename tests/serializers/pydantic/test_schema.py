from dataclasses import dataclass
from inspect import Parameter

import pytest
from dirty_equals import IsPartialDict
from pydantic import BaseModel, Field, Json

from fast_depends.library.serializer import OptionItem
from fast_depends.pydantic import PydanticSerializer
from fast_depends.pydantic._compat import PYDANTIC_V2
from tests.marks import pydanticV2
from tests.serializers.test_schema import resolve_root

REF_KEY = "$defs" if PYDANTIC_V2 else "definitions"


class User(BaseModel):
    name: str


class Group(BaseModel):
    users: list[User]


@pytest.mark.parametrize("wrapped", (True, False))
def test_nested_models(wrapped: bool) -> None:
    serializer = PydanticSerializer(use_fastdepends_errors=wrapped)(
        name="handler",
        options=[OptionItem("group", Group)],
        response_type=list[User],
    )

    schema = serializer.get_schema()

    assert schema == IsPartialDict(
        {
            "properties": {"group": {"$ref": f"#/{REF_KEY}/Group"}},
            REF_KEY: {
                "Group": IsPartialDict(
                    properties={
                        "users": IsPartialDict(
                            type="array", items={"$ref": f"#/{REF_KEY}/User"}
                        )
                    }
                ),
                "User": IsPartialDict(properties={"name": IsPartialDict(type="string")}),
            },
        }
    )

    response = serializer.get_response_schema()

    assert response == IsPartialDict(
        {
            "type": "array",
            "items": {"$ref": f"#/{REF_KEY}/User"},
            REF_KEY: {"User": IsPartialDict(required=["name"])},
        }
    )


def test_model_response() -> None:
    serializer = PydanticSerializer()(name="handler", options=[], response_type=User)

    schema = serializer.get_response_schema()

    assert schema is not None
    assert resolve_root(schema) == IsPartialDict(
        properties={"name": IsPartialDict(type="string")}
    )


def test_dataclass_response() -> None:
    @dataclass
    class Result:
        count: int

    serializer = PydanticSerializer()(name="handler", options=[], response_type=Result)

    schema = serializer.get_response_schema()

    assert schema is not None
    assert resolve_root(schema) == IsPartialDict(
        properties={"count": IsPartialDict(type="integer")}
    )


@pydanticV2
def test_response_uses_serialization_schema() -> None:
    serializer = PydanticSerializer()(
        name="handler",
        options=[OptionItem("value", Json[int])],
        response_type=Json[int],
    )

    result = serializer.response("42")

    assert PydanticSerializer.encode(result) == b"42"
    assert serializer.get_response_schema() == {"type": "integer"}
    assert serializer.get_schema() == IsPartialDict(
        properties={"value": IsPartialDict(type="string")}
    )


@pydanticV2
def test_response_includes_computed_fields() -> None:
    from pydantic import computed_field

    class Result(BaseModel):
        value: int

        @computed_field
        @property
        def twice(self) -> int:
            return self.value * 2

    serializer = PydanticSerializer()(name="handler", options=[], response_type=Result)

    result = serializer.response({"value": 21})
    schema = serializer.get_response_schema()

    assert PydanticSerializer.encode(result) == b'{"value":21,"twice":42}'
    assert schema == IsPartialDict(
        properties={
            "value": IsPartialDict(type="integer"),
            "twice": IsPartialDict(type="integer"),
        },
        required=["value", "twice"],
    )


def test_alias_constraints_and_config() -> None:
    serializer = PydanticSerializer(pydantic_config={"extra": "forbid"})(
        name="handler",
        options=[OptionItem("count", int, default_value=Field(..., alias="size", gt=0))],
        response_type=Parameter.empty,
    )

    schema = serializer.get_schema()

    assert schema == IsPartialDict(
        additionalProperties=False,
        required=["size"],
        properties={"size": IsPartialDict(type="integer", exclusiveMinimum=0)},
    )


def test_unsupported_schema_does_not_prevent_validation() -> None:
    class Custom:
        pass

    serializer = PydanticSerializer()(
        name="handler",
        options=[OptionItem("value", Custom)],
        response_type=Parameter.empty,
    )
    value = Custom()

    assert serializer({"value": value}) == {"value": value}
    schema_error: type[Exception]
    if PYDANTIC_V2:
        from pydantic.errors import PydanticInvalidForJsonSchema

        schema_error = PydanticInvalidForJsonSchema
    else:
        schema_error = ValueError

    with pytest.raises(schema_error):
        serializer.get_schema()
