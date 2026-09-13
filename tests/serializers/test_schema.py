from inspect import Parameter
from typing import Any

import pytest
from dirty_equals import IsPartialDict

from fast_depends import Provider
from fast_depends.core import build_call_model
from fast_depends.library.serializer import Serializer, SerializerProto
from tests.marks import HAS_MSGSPEC, HAS_PYDANTIC, msgspec, pydantic

if HAS_PYDANTIC:
    from fast_depends.pydantic import PydanticSerializer

if HAS_MSGSPEC:
    from fast_depends.msgspec import MsgSpecSerializer


@pytest.fixture(
    params=(
        pytest.param("pydantic", marks=pydantic),
        pytest.param("msgspec", marks=msgspec),
    )
)
def serializer_factory(request: pytest.FixtureRequest) -> SerializerProto:
    if request.param == "pydantic":
        return PydanticSerializer()
    return MsgSpecSerializer()


@pytest.fixture
def argument_serializer(serializer_factory: SerializerProto) -> Serializer:
    def handler(count: int, labels: list[str], enabled: bool = True): ...

    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=serializer_factory
    )
    assert call.serializer is not None
    return call.serializer


@pytest.fixture
def empty_serializer(serializer_factory: SerializerProto) -> Serializer:
    return serializer_factory(name="handler", options=[], response_type=Parameter.empty)


def resolve_root(schema: dict[str, Any]) -> dict[str, Any]:
    """Read a backend's root object without changing its reference structure."""
    if "$ref" in schema:
        _, definitions, name = schema["$ref"].split("/")
        return schema[definitions][name]
    return schema


def test_integer_argument(argument_serializer: Serializer) -> None:
    schema = resolve_root(argument_serializer.get_schema())

    assert schema == IsPartialDict(
        properties=IsPartialDict(count=IsPartialDict(type="integer"))
    )


def test_list_argument(argument_serializer: Serializer) -> None:
    schema = resolve_root(argument_serializer.get_schema())

    assert schema == IsPartialDict(
        properties=IsPartialDict(
            labels=IsPartialDict(type="array", items={"type": "string"})
        )
    )


def test_boolean_argument(argument_serializer: Serializer) -> None:
    schema = resolve_root(argument_serializer.get_schema())

    assert schema == IsPartialDict(
        properties=IsPartialDict(enabled=IsPartialDict(type="boolean"))
    )


def test_argument_default(argument_serializer: Serializer) -> None:
    schema = resolve_root(argument_serializer.get_schema())

    assert schema == IsPartialDict(
        properties=IsPartialDict(enabled=IsPartialDict(default=True))
    )


def test_required_arguments(argument_serializer: Serializer) -> None:
    schema = resolve_root(argument_serializer.get_schema())

    assert schema == IsPartialDict(required=["count", "labels"])


def test_empty_arguments(empty_serializer: Serializer) -> None:
    schema = resolve_root(empty_serializer.get_schema())

    assert schema == IsPartialDict(type="object", properties={})


def test_empty_arguments_have_no_required_fields(empty_serializer: Serializer) -> None:
    schema = resolve_root(empty_serializer.get_schema())

    assert not schema.get("required")


def test_response(serializer_factory: SerializerProto) -> None:
    def handler() -> list[int]: ...

    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=serializer_factory
    )
    assert call.serializer is not None
    schema = call.serializer.get_response_schema()

    assert schema == IsPartialDict(type="array", items={"type": "integer"})


def test_unannotated_response(serializer_factory: SerializerProto) -> None:
    def handler(): ...

    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=serializer_factory
    )
    assert call.serializer is not None
    assert call.serializer.get_response_schema() is None


def test_none_response(serializer_factory: SerializerProto) -> None:
    def handler() -> None: ...

    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=serializer_factory
    )
    assert call.serializer is not None
    schema = call.serializer.get_response_schema()

    assert schema == IsPartialDict(type="null")


def test_disabled_response(serializer_factory: SerializerProto) -> None:
    def handler() -> int: ...

    call = build_call_model(
        handler,
        dependency_provider=Provider(),
        serializer_cls=serializer_factory,
        serialize_result=False,
    )
    assert call.serializer is not None
    assert call.serializer.get_response_schema() is None


def test_explicit_none_response_type(serializer_factory: SerializerProto) -> None:
    serializer = serializer_factory(name="handler", options=[], response_type=None)

    schema = serializer.get_response_schema()

    assert schema == IsPartialDict(type="null")


def test_any_response(serializer_factory: SerializerProto) -> None:
    serializer = serializer_factory(name="handler", options=[], response_type=Any)

    schema = serializer.get_response_schema()

    assert schema is not None
    assert "type" not in schema
