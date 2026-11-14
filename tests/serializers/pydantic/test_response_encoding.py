import inspect
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, Any

import pytest
from pydantic import (
    BaseModel,
    PlainSerializer,
    TypeAdapter,
    WrapSerializer,
    model_serializer,
)
from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic.errors import PydanticUserError
from typing_extensions import TypeAliasType, TypedDict

from fast_depends import Depends, Provider, inject
from fast_depends.core import build_call_model
from fast_depends.pydantic import PydanticSerializer
from tests.serializers.test_schema import resolve_root


@pytest.mark.parametrize("wrapped", (True, False))
@pytest.mark.parametrize("plain", (True, False))
def test_typed_response_public_api_preserves_python_values(wrapped, plain):
    annotation = Annotated[
        int,
        (
            PlainSerializer(str, return_type=str)
            if plain
            else WrapSerializer(
                lambda value, handler: str(handler(value)), return_type=str
            )
        ),
    ]
    factory = PydanticSerializer(use_fastdepends_errors=wrapped)
    provider = Provider()

    def dependency(count: int) -> int:
        return count + 1

    def answer(value: int = Depends(dependency)) -> annotation:
        return str(value)

    call = build_call_model(answer, dependency_provider=provider, serializer_cls=factory)
    answer = inject(serializer_cls=factory)(answer, model=call)
    value = answer(count="41")
    assert type(value) is int
    assert value == 42
    assert factory.encode(value) == b"42"
    assert call.serializer.encode_response(value) == b'"42"'
    assert call.serializer.get_response_schema() == {"type": "string"}


@pytest.mark.anyio
async def test_async_response_uses_own_adapter():
    factory = PydanticSerializer()
    annotation = Annotated[int, PlainSerializer(str, return_type=str)]

    async def as_text(value: int) -> annotation:
        return value

    async def as_number(value: int) -> int:
        return value

    calls = [
        build_call_model(f, dependency_provider=Provider(), serializer_cls=factory)
        for f in (as_text, as_number)
    ]
    handlers = [
        inject(serializer_cls=factory)(f, model=c)
        for f, c in zip((as_text, as_number), calls, strict=True)
    ]
    for _ in range(2):
        text_value, number_value = await handlers[0]("42"), await handlers[1]("42")
        assert text_value == number_value == 42
        assert calls[0].serializer.encode_response(text_value) == b'"42"'
        assert calls[1].serializer.encode_response(number_value) == b"42"
        assert factory.encode(text_value) == b"42"


@pytest.mark.parametrize("annotation", (int, inspect.Parameter.empty))
def test_disabled_result_validation_keeps_generic_encoding(annotation):
    factory = PydanticSerializer(pydantic_config={"ser_json_timedelta": "float"})

    def handler() -> annotation:
        return {"duration": timedelta(seconds=90)}

    call = build_call_model(
        handler,
        dependency_provider=Provider(),
        serializer_cls=factory,
        serialize_result=False,
    )
    wrapped = inject(serializer_cls=factory)(handler, model=call)
    value = wrapped()
    assert value == {"duration": timedelta(seconds=90)}
    assert (
        call.serializer.encode_response(value)
        == factory.encode(value)
        == b'{"duration":90.0}'
    )
    assert call.serializer.get_response_schema() is None
    assert call.serializer.encode_response(b"raw") == b"raw"


def test_missing_annotation_keeps_generic_encoding():
    factory = PydanticSerializer()

    def handler():
        return 42

    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=factory
    )
    assert call.serializer.encode_response(handler()) == b"42"
    assert call.serializer.get_response_schema() is None


@pytest.mark.parametrize("plain", (True, False))
def test_typed_bytes_honor_annotation_serializer(plain):
    annotation = Annotated[
        bytes,
        (
            PlainSerializer(lambda value: value.hex(), return_type=str)
            if plain
            else WrapSerializer(lambda value, handler: "wrapped", return_type=str)
        ),
    ]
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=annotation)
    assert factory.encode(b"ab") == b"ab"
    assert serializer.encode_response(serializer.response(b"ab")) == (
        b'"6162"' if plain else b'"wrapped"'
    )
    assert serializer.get_response_schema() == {"type": "string"}


@pytest.mark.parametrize("kind", ("typed_dict", "dataclass", "pydantic_dataclass"))
@pytest.mark.parametrize("nested", (True, False))
@pytest.mark.parametrize("own_format", ("hex", "base64"))
def test_structure_config_precedence_matches_typeadapter(kind, nested, own_format):
    if kind == "typed_dict":

        class Record(TypedDict):
            value: bytes
    else:

        @dataclass
        class Record:
            value: bytes

    Record.__pydantic_config__ = {"ser_json_bytes": own_format}
    if kind == "pydantic_dataclass":
        Record = pydantic_dataclass(Record)
    annotation = list[Record] if nested else Record
    config = {"ser_json_bytes": "base64"}
    factory = PydanticSerializer(pydantic_config=config)
    serializer = factory(name="handler", options=[], response_type=annotation)
    data = [{"value": b"ab"}] if nested else {"value": b"ab"}
    adapter = (
        TypeAdapter(annotation, config=config) if nested else TypeAdapter(annotation)
    )
    encoded = serializer.encode_response(serializer.response(data))
    assert encoded == adapter.dump_json(adapter.validate_python(data), by_alias=True)
    expected = (
        ("YWI=" if nested else "ab")
        if kind == "typed_dict"
        else ("YWI=" if own_format == "base64" else "6162")
    )
    assert json.loads(encoded) == (
        [{"value": expected}] if nested else {"value": expected}
    )
    schema = serializer.get_response_schema()
    item = resolve_root({**schema, **schema["items"]}) if nested else resolve_root(schema)
    assert item["properties"]["value"]["format"] == (
        "base64url" if expected == "YWI=" else "binary"
    )


SharedBytes = TypeAliasType("SharedBytes", bytes)


class SharedRecord(TypedDict):
    value: SharedBytes


@pytest.mark.parametrize("reverse", (True, False))
def test_shared_typed_dict_under_distinct_configs(reverse):
    class HexModel(BaseModel):
        model_config = {"ser_json_bytes": "hex"}
        record: SharedRecord

    annotation = (
        tuple[HexModel, SharedRecord] if reverse else tuple[SharedRecord, HexModel]
    )
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=annotation)
    values = ({"record": {"value": b"ab"}}, {"value": b"ab"})
    encoded = json.loads(
        serializer.encode_response(
            serializer.response(values if reverse else values[::-1])
        )
    )
    schema = serializer.get_response_schema()
    for index, part in enumerate(schema["prefixItems"]):
        part = resolve_root({**schema, **part})
        data = encoded[index]
        if "record" in data:
            part = resolve_root({**schema, **part["properties"]["record"]})
            data = data["record"]
        field = resolve_root({**schema, **part["properties"]["value"]})
        assert field["format"] == ("base64url" if data["value"] == "YWI=" else "binary")


@pytest.mark.parametrize("plain", (True, False))
def test_outer_serializer_on_reused_model_reference(plain):
    class Model(BaseModel):
        value: int

    annotation = Annotated[
        Model,
        (
            PlainSerializer(lambda value: "replaced", return_type=str)
            if plain
            else WrapSerializer(lambda value, handler: "replaced", return_type=str)
        ),
    ]
    serializer = PydanticSerializer()(
        name="handler", options=[], response_type=tuple[Model, annotation]
    )
    result = serializer.response(({"value": 1}, {"value": 2}))
    assert json.loads(serializer.encode_response(result)) == [{"value": 1}, "replaced"]
    schema = serializer.get_response_schema()
    assert schema["prefixItems"][1] == {"type": "string"}


def test_response_adapter_does_not_suppress_other_user_errors():
    class Invalid:
        @classmethod
        def __get_pydantic_core_schema__(cls, source: Any, handler: Any):
            raise PydanticUserError(
                "invalid response annotation", code="invalid-for-json-schema"
            )

    with pytest.raises(PydanticUserError, match="invalid response annotation"):
        PydanticSerializer()(name="handler", options=[], response_type=Invalid)


def test_untyped_response_preserves_custom_factory_encoder():
    class Factory(PydanticSerializer):
        @staticmethod
        def encode(value):
            return b"custom"

    factory = Factory()
    serializer = factory(
        name="handler", options=[], response_type=inspect.Parameter.empty
    )
    assert serializer.encode_response(b"raw") == factory.encode(b"raw") == b"custom"


def test_typed_model_response_uses_declared_fields():
    class Result(BaseModel):
        value: int

    class ExtendedResult(Result):
        extra: str

    factory = PydanticSerializer()
    serializer = factory(name="handler", options=[], response_type=Result)
    result = ExtendedResult(value=42, extra="extra")
    assert serializer.response(result) is result
    assert factory.encode(result) == b'{"value":42,"extra":"extra"}'
    assert serializer.encode_response(result) == b'{"value":42}'
    assert list(serializer.get_response_schema()["properties"]) == ["value"]


class Opaque:
    pass


OpaqueAlias = TypeAliasType("OpaqueAlias", Opaque)


@pytest.mark.parametrize("nested", (True, False))
def test_annotation_serializer_defines_otherwise_unsupported_schema(nested):
    annotation = Annotated[
        OpaqueAlias, PlainSerializer(lambda value: "ok", return_type=str)
    ]
    serializer = PydanticSerializer()(
        name="handler",
        options=[],
        response_type=list[annotation] if nested else annotation,
    )
    value = [Opaque()] if nested else Opaque()
    result = serializer.response(value)
    assert serializer.encode_response(result) == (b'["ok"]' if nested else b'"ok"')
    assert serializer.get_response_schema() == (
        {"type": "array", "items": {"type": "string"}} if nested else {"type": "string"}
    )


@pytest.mark.parametrize("nested", (True, False))
@pytest.mark.parametrize("outer", (True, False))
def test_model_serializer_return_encoding_matches_adapter(nested, outer):
    class Result(BaseModel):
        model_config = {"ser_json_bytes": "base64"}
        value: int

        @model_serializer
        def serialize(self) -> bytes:
            return b"ab"

    annotation = (
        Annotated[Result, PlainSerializer(lambda value: b"ab", return_type=bytes)]
        if outer
        else Result
    )
    annotation = list[annotation] if nested else annotation
    serializer = PydanticSerializer()(
        name="handler", options=[], response_type=annotation
    )
    result = serializer.response([{"value": 42}] if nested else {"value": 42})
    expected = "YWI=" if not nested and not outer else "ab"
    assert json.loads(serializer.encode_response(result)) == (
        [expected] if nested else expected
    )
    schema = serializer.get_response_schema()
    item = schema["items"] if nested else schema
    item = resolve_root({**item, "$defs": schema.get("$defs", {})})
    item.pop("$defs", None)
    assert item == {
        "type": "string",
        "format": "base64url" if expected == "YWI=" else "binary",
    }
