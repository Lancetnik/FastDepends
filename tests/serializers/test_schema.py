from inspect import Parameter
from typing import Any

import pytest
from dirty_equals import IsPartialDict

from fast_depends import Provider
from fast_depends.core import build_call_model
from fast_depends.library.serializer import SerializerProto


@pytest.fixture(params=("pydantic", "msgspec"))
def serializer_factory(request: pytest.FixtureRequest) -> SerializerProto:
    pytest.importorskip(request.param)
    if request.param == "pydantic":
        from fast_depends.pydantic import PydanticSerializer

        return PydanticSerializer()

    from fast_depends.msgspec import MsgSpecSerializer

    return MsgSpecSerializer()


def resolve_root(schema: dict[str, Any]) -> dict[str, Any]:
    """Read a backend's root object without changing its reference structure."""
    if "$ref" in schema:
        _, definitions, name = schema["$ref"].split("/")
        return schema[definitions][name]
    return schema


def test_arguments(serializer_factory: SerializerProto) -> None:
    def handler(count: int, labels: list[str], enabled: bool = True): ...

    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=serializer_factory
    )
    assert call.serializer is not None
    schema = resolve_root(call.serializer.get_schema())

    assert schema == IsPartialDict(
        type="object",
        required=["count", "labels"],
        properties={
            "count": IsPartialDict(type="integer"),
            "labels": IsPartialDict(type="array", items={"type": "string"}),
            "enabled": IsPartialDict(type="boolean", default=True),
        },
    )


def test_empty_arguments(serializer_factory: SerializerProto) -> None:
    serializer = serializer_factory(
        name="handler",
        options=[],
        response_type=Parameter.empty,
    )

    schema = resolve_root(serializer.get_schema())

    assert schema == IsPartialDict(type="object", properties={})
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
