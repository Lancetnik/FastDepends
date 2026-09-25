from dataclasses import dataclass
from inspect import Parameter

import pytest
from dirty_equals import IsPartialDict
from pydantic import BaseModel, Field, Json

from fast_depends.library.serializer import OptionItem, Serializer
from fast_depends.pydantic import PydanticSerializer
from fast_depends.pydantic._compat import PYDANTIC_V2
from tests.marks import pydanticV2
from tests.serializers.test_schema import resolve_root

if PYDANTIC_V2:
    from pydantic import computed_field
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
