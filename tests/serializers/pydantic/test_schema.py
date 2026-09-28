import json
from dataclasses import dataclass
from inspect import Parameter
from typing import Annotated

import pytest
from dirty_equals import IsPartialDict
from pydantic import BaseModel, Field, Json

from fast_depends.library.serializer import OptionItem, Serializer
from fast_depends.pydantic import PydanticSerializer
from fast_depends.pydantic._compat import PYDANTIC_V2
from tests.marks import pydanticV2
from tests.serializers.test_schema import resolve_root

if PYDANTIC_V2:
    from pydantic import PlainSerializer, WrapSerializer, computed_field
    from pydantic.dataclasses import dataclass as pydantic_dataclass
    from pydantic.errors import PydanticInvalidForJsonSchema

REF_KEY = "$defs" if PYDANTIC_V2 else "definitions"
SCHEMA_ERROR = PydanticInvalidForJsonSchema if PYDANTIC_V2 else ValueError


class User(BaseModel):
    name: str


class Group(BaseModel):
    users: list[User]


class Custom:
    pass


@pytest.fixture(params=(True, False), ids=("wrapped", "unwrapped"))
def nested_serializer(request: pytest.FixtureRequest) -> Serializer:
    return PydanticSerializer(use_fastdepends_errors=request.param)(
        name="handler",
        options=[OptionItem("group", Group)],
        response_type=list[User],
    )


@pytest.fixture
def json_serializer() -> Serializer:
    return PydanticSerializer()(
        name="handler",
        options=[OptionItem("value", Json[int])],
        response_type=Json[int],
    )


@pytest.fixture
def computed_response_serializer() -> Serializer:
    class Result(BaseModel):
        value: int

        @computed_field
        @property
        def twice(self) -> int:
            return self.value * 2

    return PydanticSerializer()(name="handler", options=[], response_type=Result)


@pytest.fixture
def aliased_serializer() -> Serializer:
    return PydanticSerializer()(
        name="handler",
        options=[OptionItem("count", int, default_value=Field(..., alias="size"))],
        response_type=Parameter.empty,
    )


@pytest.fixture
def custom_serializer() -> Serializer:
    return PydanticSerializer()(
        name="handler",
        options=[OptionItem("value", Custom)],
        response_type=Parameter.empty,
    )


def test_nested_models(nested_serializer: Serializer) -> None:
    schema = nested_serializer.get_schema()

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


def test_list_of_models_response(nested_serializer: Serializer) -> None:
    schema = nested_serializer.get_response_schema()

    assert schema == IsPartialDict(
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


@pytest.mark.parametrize("wrapped", (True, False))
@pytest.mark.parametrize("nested", (True, False))
def test_response_alias_matches_encoded_model(wrapped: bool, nested: bool) -> None:
    class Result(BaseModel):
        value: int = Field(alias="external")

    serializer = PydanticSerializer(use_fastdepends_errors=wrapped)(
        name="handler", options=[], response_type=list[Result] if nested else Result
    )
    value = [{"external": 1}] if nested else {"external": 1}
    encoded = json.loads(PydanticSerializer.encode(serializer.response(value)))
    schema = serializer.get_response_schema()
    assert schema is not None
    result_schema = schema[REF_KEY]["Result"] if nested else resolve_root(schema)
    assert result_schema["required"] == list(encoded[0] if nested else encoded)


@pydanticV2
@pytest.mark.parametrize("wrapped", (True, False))
@pytest.mark.parametrize("nested", (True, False))
@pytest.mark.parametrize("when_used", ("always", "json"))
@pytest.mark.parametrize("plain", (True, False))
def test_response_annotation_serializer_matches_encoding(
    wrapped: bool, nested: bool, when_used: str, plain: bool
) -> None:
    serializer_hook = (
        PlainSerializer(str, return_type=str, when_used=when_used)
        if plain
        else WrapSerializer(lambda value, handler: str(handler(value)), return_type=str)
    )
    result_type = Annotated[int, serializer_hook]
    serializer = PydanticSerializer(use_fastdepends_errors=wrapped)(
        name="handler",
        options=[],
        response_type=list[result_type] if nested else result_type,
    )
    result = serializer.response([1] if nested else 1)
    schema = serializer.get_response_schema()
    assert schema == (
        {"type": "array", "items": {"type": "integer"}} if nested else {"type": "integer"}
    )
    assert json.loads(PydanticSerializer.encode(result)) == ([1] if nested else 1)


@pydanticV2
@pytest.mark.parametrize("model_kind", ("model", "dataclass", "plain_dataclass"))
@pytest.mark.parametrize("outer_serializer", (True, False))
def test_response_preserves_serializer_carried_by_value(model_kind, outer_serializer):
    class Result(BaseModel):
        value: Annotated[int, PlainSerializer(str, return_type=str)]

    if model_kind != "model":

        @dataclass
        class Record:
            value: Annotated[int, PlainSerializer(str, return_type=str)]

        Result = pydantic_dataclass(Record) if model_kind == "dataclass" else Record

    annotation = (
        Annotated[Result, PlainSerializer(lambda value: "ignored", return_type=str)]
        if outer_serializer
        else Result
    )
    serializer = PydanticSerializer()(
        name="handler", options=[], response_type=annotation
    )
    schema = serializer.get_response_schema()
    encoded = json.loads(PydanticSerializer.encode(serializer.response({"value": 1})))
    assert schema is not None
    expected_type = "integer" if model_kind == "plain_dataclass" else "string"
    assert resolve_root(schema)["properties"]["value"]["type"] == expected_type
    assert encoded == {"value": 1 if model_kind == "plain_dataclass" else "1"}


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
def test_response_uses_serialization_schema(json_serializer: Serializer) -> None:
    assert json_serializer.get_response_schema() == {"type": "integer"}


@pydanticV2
def test_arguments_use_validation_schema(json_serializer: Serializer) -> None:
    assert json_serializer.get_schema() == IsPartialDict(
        properties={"value": IsPartialDict(type="string")}
    )


@pydanticV2
def test_json_response_encoding(json_serializer: Serializer) -> None:
    result = json_serializer.response("42")

    assert PydanticSerializer.encode(result) == b"42"


@pydanticV2
def test_response_includes_computed_fields(
    computed_response_serializer: Serializer,
) -> None:
    schema = computed_response_serializer.get_response_schema()

    assert schema == IsPartialDict(
        properties=IsPartialDict(twice=IsPartialDict(type="integer"))
    )


@pydanticV2
def test_computed_fields_are_required(computed_response_serializer: Serializer) -> None:
    schema = computed_response_serializer.get_response_schema()

    assert schema == IsPartialDict(required=["value", "twice"])


@pydanticV2
def test_computed_fields_are_encoded(computed_response_serializer: Serializer) -> None:
    result = computed_response_serializer.response({"value": 21})

    assert PydanticSerializer.encode(result) == b'{"value":21,"twice":42}'


def test_argument_alias(aliased_serializer: Serializer) -> None:
    assert aliased_serializer.get_schema() == IsPartialDict(
        properties={"size": IsPartialDict(type="integer")}
    )


def test_required_argument_uses_alias(aliased_serializer: Serializer) -> None:
    assert aliased_serializer.get_schema() == IsPartialDict(required=["size"])


def test_argument_constraint() -> None:
    serializer = PydanticSerializer()(
        name="handler",
        options=[OptionItem("count", int, default_value=Field(..., gt=0))],
        response_type=Parameter.empty,
    )

    assert serializer.get_schema() == IsPartialDict(
        properties={"count": IsPartialDict(exclusiveMinimum=0)}
    )


def test_schema_preserves_config() -> None:
    serializer = PydanticSerializer(pydantic_config={"extra": "forbid"})(
        name="handler", options=[], response_type=Parameter.empty
    )

    assert serializer.get_schema() == IsPartialDict(additionalProperties=False)


def test_custom_type_validation(custom_serializer: Serializer) -> None:
    value = Custom()

    assert custom_serializer({"value": value}) == {"value": value}


def test_unsupported_schema_type(custom_serializer: Serializer) -> None:
    with pytest.raises(SCHEMA_ERROR):
        custom_serializer.get_schema()
