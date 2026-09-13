from inspect import Parameter
from typing import Annotated

import msgspec
import pytest
from dirty_equals import IsPartialDict

from fast_depends.library.serializer import OptionItem, Serializer
from fast_depends.msgspec import MsgSpecSerializer
from tests.serializers.test_schema import resolve_root


class User(msgspec.Struct):
    name: str


class Group(msgspec.Struct):
    users: list[User]


class Node(msgspec.Struct):
    children: list["Node"] = msgspec.field(default_factory=list)


class Custom:
    pass


@pytest.fixture(params=(True, False), ids=("wrapped", "unwrapped"))
def nested_serializer(request: pytest.FixtureRequest) -> Serializer:
    return MsgSpecSerializer(use_fastdepends_errors=request.param)(
        name="handler",
        options=[OptionItem("group", Group)],
        response_type=list[User],
    )


@pytest.fixture
def aliased_serializer() -> Serializer:
    return MsgSpecSerializer()(
        name="handler",
        options=[OptionItem("count", int, default_value=msgspec.field(name="size"))],
        response_type=Parameter.empty,
    )


@pytest.fixture
def custom_serializer() -> Serializer:
    return MsgSpecSerializer()(
        name="handler",
        options=[OptionItem("value", Custom)],
        response_type=Parameter.empty,
    )


def test_nested_structs(nested_serializer: Serializer) -> None:
    schema = nested_serializer.get_schema()

    assert schema == IsPartialDict(
        {
            "$ref": "#/$defs/handler",
            "$defs": {
                "handler": IsPartialDict(properties={"group": {"$ref": "#/$defs/Group"}}),
                "Group": IsPartialDict(
                    properties={
                        "users": {"type": "array", "items": {"$ref": "#/$defs/User"}}
                    }
                ),
                "User": IsPartialDict(properties={"name": {"type": "string"}}),
            },
        }
    )


def test_list_of_structs_response(nested_serializer: Serializer) -> None:
    schema = nested_serializer.get_response_schema()

    assert schema == IsPartialDict(
        {
            "type": "array",
            "items": {"$ref": "#/$defs/User"},
            "$defs": {"User": IsPartialDict(required=["name"])},
        }
    )


def test_recursive_struct() -> None:
    serializer = MsgSpecSerializer()(name="handler", options=[], response_type=Node)

    schema = serializer.get_response_schema()

    assert schema == IsPartialDict(
        {
            "$ref": "#/$defs/Node",
            "$defs": {
                "Node": IsPartialDict(
                    properties={
                        "children": IsPartialDict(
                            type="array", items={"$ref": "#/$defs/Node"}
                        )
                    }
                )
            },
        }
    )


def test_argument_alias(aliased_serializer: Serializer) -> None:
    schema = resolve_root(aliased_serializer.get_schema())

    assert schema == IsPartialDict(properties={"size": IsPartialDict(type="integer")})


def test_required_argument_uses_alias(aliased_serializer: Serializer) -> None:
    schema = resolve_root(aliased_serializer.get_schema())

    assert schema == IsPartialDict(required=["size"])


def test_argument_constraint() -> None:
    serializer = MsgSpecSerializer()(
        name="handler",
        options=[OptionItem("count", Annotated[int, msgspec.Meta(gt=0)])],
        response_type=Parameter.empty,
    )

    schema = resolve_root(serializer.get_schema())

    assert schema == IsPartialDict(
        properties={"count": IsPartialDict(exclusiveMinimum=0)}
    )


def test_custom_type_validation(custom_serializer: Serializer) -> None:
    value = Custom()

    assert custom_serializer({"value": value}) == {"value": value}


def test_unsupported_schema_type(custom_serializer: Serializer) -> None:
    with pytest.raises(TypeError):
        custom_serializer.get_schema()
