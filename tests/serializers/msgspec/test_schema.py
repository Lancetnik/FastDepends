from inspect import Parameter
from typing import Annotated

import msgspec
import pytest
from dirty_equals import IsPartialDict

from fast_depends.library.serializer import OptionItem
from fast_depends.msgspec import MsgSpecSerializer
from tests.serializers.test_schema import resolve_root


class User(msgspec.Struct):
    name: str


class Group(msgspec.Struct):
    users: list[User]


class Node(msgspec.Struct):
    children: list["Node"] = msgspec.field(default_factory=list)


@pytest.mark.parametrize("wrapped", (True, False))
def test_nested_structs(wrapped: bool) -> None:
    serializer = MsgSpecSerializer(use_fastdepends_errors=wrapped)(
        name="handler",
        options=[OptionItem("group", Group)],
        response_type=list[User],
    )

    schema = serializer.get_schema()

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

    response = serializer.get_response_schema()

    assert response == IsPartialDict(
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


def test_alias_and_constraints() -> None:
    serializer = MsgSpecSerializer()(
        name="handler",
        options=[
            OptionItem(
                "count",
                Annotated[int, msgspec.Meta(gt=0)],
                default_value=msgspec.field(name="size"),
            )
        ],
        response_type=Parameter.empty,
    )

    schema = resolve_root(serializer.get_schema())

    assert schema == IsPartialDict(
        required=["size"],
        properties={"size": IsPartialDict(type="integer", exclusiveMinimum=0)},
    )


def test_unsupported_schema_does_not_prevent_validation() -> None:
    class Custom:
        pass

    serializer = MsgSpecSerializer()(
        name="handler",
        options=[OptionItem("value", Custom)],
        response_type=Parameter.empty,
    )
    value = Custom()

    assert serializer({"value": value}) == {"value": value}
    with pytest.raises(TypeError):
        serializer.get_schema()
