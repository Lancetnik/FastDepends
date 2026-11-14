import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from inspect import Parameter
from typing import Annotated, Any, Union

import pytest
from dirty_equals import IsPartialDict
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    Discriminator,
    Field,
    Json,
    PlainSerializer,
    Tag,
    WrapSerializer,
    WrapValidator,
    computed_field,
)
from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic.errors import PydanticInvalidForJsonSchema
from pydantic_core import core_schema
from typing_extensions import TypeAliasType, TypedDict

from fast_depends.library.serializer import OptionItem, Serializer
from fast_depends.pydantic import PydanticSerializer
from tests.serializers.test_schema import resolve_root

REF_KEY = "$defs"
SCHEMA_ERROR = PydanticInvalidForJsonSchema


def resolve_part(schema, part):
    return resolve_root({**schema, **part}) if "$ref" in part else part


class User(BaseModel):
    name: str


class Group(BaseModel):
    users: list[User]


class Custom:
    pass


ResponseSpan = TypeAliasType("ResponseSpan", timedelta)
ResponseBytes = TypeAliasType("ResponseBytes", bytes)
ByteTree = TypeAliasType("ByteTree", bytes | list["ByteTree"])
ByteCycle = TypeAliasType("ByteCycle", Union[bytes, "ByteCycle"])


class TimedResponse(BaseModel):
    model_config = {"ser_json_timedelta": "float"}
    value: ResponseSpan


class BinaryResponse(BaseModel):
    model_config = {"ser_json_bytes": "hex"}
    value: ResponseBytes


class FirstRecursiveResponse(TypedDict):
    value: Annotated[int, Field(alias="external")]
    child: "SecondRecursiveResponse | None"


class SecondRecursiveResponse(TypedDict):
    value: Annotated[int, Field(alias="external")]
    child: "FirstRecursiveResponse | None"


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


@pytest.fixture(params=("typed_dict", "dataclass", "pydantic_dataclass"))
def aliased_response_type(request):
    if request.param == "typed_dict":

        class Result(TypedDict):
            value: Annotated[int, Field(alias="external")]

        return Result

    @dataclass
    class Record:
        value: Annotated[int, Field(alias="external")]

    return pydantic_dataclass(Record) if request.param == "pydantic_dataclass" else Record


@pytest.mark.parametrize("wrapped", (True, False))
@pytest.mark.parametrize("nested", (True, False))
@pytest.mark.parametrize("keyword", ("properties", "required"))
def test_response_alias_matches_encoded_structure(
    aliased_response_type, wrapped, nested, keyword
):
    serializer = PydanticSerializer(use_fastdepends_errors=wrapped)(
        name="handler",
        options=[],
        response_type=list[aliased_response_type] if nested else aliased_response_type,
    )
    value = [{"external": 1}] if nested else {"external": 1}
    encoded = json.loads(PydanticSerializer.encode(serializer.response(value)))
    schema = serializer.get_response_schema()
    result_schema = (
        resolve_root({**schema, **schema["items"]}) if nested else resolve_root(schema)
    )

    assert list(result_schema[keyword]) == list(encoded[0] if nested else encoded)


@pytest.mark.parametrize("model_first", (True, False))
def test_response_alias_distinguishes_structure_inside_model(
    aliased_response_type, model_first
):
    class Envelope(BaseModel):
        result: aliased_response_type

    result_type = (
        tuple[Envelope, aliased_response_type]
        if model_first
        else tuple[aliased_response_type, Envelope]
    )
    serializer = PydanticSerializer()(
        name="handler", options=[], response_type=result_type
    )
    values = ({"result": {"external": 1}}, {"external": 1})
    encoded = json.loads(
        PydanticSerializer.encode(
            serializer.response(values if model_first else values[::-1])
        )
    )
    schema = serializer.get_response_schema()
    names = []
    for index, item in enumerate(schema["prefixItems"]):
        result_schema = resolve_root({**schema, **item})
        if (index == 0) == model_first:
            result_schema = resolve_root(
                {**schema, **result_schema["properties"]["result"]}
            )
            encoded[index] = encoded[index]["result"]
        names.append(list(result_schema["properties"]))

    assert names == [list(value) for value in encoded]


@pytest.mark.parametrize("reverse", (True, False))
def test_response_alias_preserves_mutually_recursive_references(reverse):
    result_type = (
        tuple[SecondRecursiveResponse, FirstRecursiveResponse]
        if reverse
        else tuple[FirstRecursiveResponse, SecondRecursiveResponse]
    )
    serializer = PydanticSerializer()(
        name="handler", options=[], response_type=result_type
    )
    value = {"external": 1, "child": {"external": 2, "child": None}}
    encoded = json.loads(PydanticSerializer.encode(serializer.response((value, value))))
    schema = serializer.get_response_schema()
    child_names = []
    for item in schema["prefixItems"]:
        result_schema = resolve_root({**schema, **item})
        child = result_schema["properties"]["child"]["anyOf"][0]
        child_names.append(list(resolve_root({**schema, **child})["properties"]))

    assert child_names == [list(value["child"]) for value in encoded]


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


def test_response_uses_serialization_schema(json_serializer: Serializer) -> None:
    assert json_serializer.get_response_schema() == {"type": "integer"}


def test_arguments_use_validation_schema(json_serializer: Serializer) -> None:
    assert json_serializer.get_schema() == IsPartialDict(
        properties={"value": IsPartialDict(type="string")}
    )


def test_json_response_encoding(json_serializer: Serializer) -> None:
    result = json_serializer.response("42")

    assert PydanticSerializer.encode(result) == b"42"


def test_response_includes_computed_fields(
    computed_response_serializer: Serializer,
) -> None:
    schema = computed_response_serializer.get_response_schema()

    assert schema == IsPartialDict(
        properties=IsPartialDict(twice=IsPartialDict(type="integer"))
    )


def test_computed_fields_are_required(computed_response_serializer: Serializer) -> None:
    schema = computed_response_serializer.get_response_schema()

    assert schema == IsPartialDict(required=["value", "twice"])


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


@pytest.mark.parametrize("wrapped", (True, False))
@pytest.mark.parametrize("nested", (True, False))
@pytest.mark.parametrize(
    "config, annotation, value, encoded, value_schema",
    [
        (
            {},
            timedelta,
            timedelta(seconds=90),
            "PT1M30S",
            {"type": "string", "format": "duration"},
        ),
        (
            {"ser_json_timedelta": "float"},
            timedelta,
            timedelta(seconds=90),
            90.0,
            {"type": "number"},
        ),
        (
            {"ser_json_temporal": "seconds"},
            datetime,
            datetime(2026, 1, 1),
            1767225600.0,
            {"type": "number"},
        ),
        (
            {"ser_json_temporal": "milliseconds"},
            date,
            date(2026, 1, 1),
            1767225600000.0,
            {"type": "number"},
        ),
        (
            {"ser_json_temporal": "seconds"},
            time,
            time(12, 30),
            45000.0,
            {"type": "number"},
        ),
        (
            {"ser_json_temporal": "milliseconds"},
            timedelta,
            timedelta(seconds=90),
            90000.0,
            {"type": "number"},
        ),
        (
            {"ser_json_temporal": "iso8601", "ser_json_timedelta": "float"},
            timedelta,
            timedelta(seconds=90),
            "PT1M30S",
            {"type": "string", "format": "duration"},
        ),
    ],
)
def test_temporal_response_describes_configured_encoding(
    wrapped, nested, config, annotation, value, encoded, value_schema
):
    factory = PydanticSerializer(pydantic_config=config, use_fastdepends_errors=wrapped)
    serializer = factory(
        name="handler",
        options=[],
        response_type=list[annotation] if nested else annotation,
    )
    wire_value = json.loads(
        factory.encode(serializer.response([value] if nested else value))
    )
    assert wire_value == ([encoded] if nested else encoded)
    schema = serializer.get_response_schema()
    assert (schema["items"] if nested else schema) == value_schema


@pytest.mark.parametrize("model_first", (True, False))
def test_configured_response_alias_matches_model_encoding(model_first):
    factory = PydanticSerializer(pydantic_config={"ser_json_timedelta": "float"})
    response_type = (
        tuple[TimedResponse, ResponseSpan]
        if model_first
        else tuple[ResponseSpan, TimedResponse]
    )
    serializer = factory(name="handler", options=[], response_type=response_type)
    span = timedelta(seconds=90)
    values = ({"value": span}, span) if model_first else (span, {"value": span})

    assert json.loads(factory.encode(serializer.response(values))) == (
        [{"value": 90.0}, 90.0] if model_first else [90.0, {"value": 90.0}]
    )
    schema = serializer.get_response_schema()
    item = schema["prefixItems"][1 if model_first else 0]
    assert resolve_root({**schema, **item}) == {"type": "number"}


@pytest.mark.parametrize("model_first", (True, False))
def test_response_alias_keeps_distinct_model_encoding_config(model_first):
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    response_type = (
        tuple[BinaryResponse, ResponseBytes]
        if model_first
        else tuple[ResponseBytes, BinaryResponse]
    )
    serializer = factory(name="handler", options=[], response_type=response_type)
    values = ({"value": b"ab"}, b"ab") if model_first else (b"ab", {"value": b"ab"})

    assert json.loads(factory.encode(serializer.response(values))) == (
        [{"value": "6162"}, "YWI="] if model_first else ["YWI=", {"value": "6162"}]
    )
    schema = serializer.get_response_schema()
    generic = schema["prefixItems"][1 if model_first else 0]
    model = schema["prefixItems"][0 if model_first else 1]
    model_schema = resolve_root({**schema, **model})
    assert resolve_root({**schema, **generic}) == {
        "type": "string",
        "format": "base64url",
    }
    assert resolve_root({**schema, **model_schema["properties"]["value"]}) == {
        "type": "string",
        "format": "binary",
    }


@pytest.mark.parametrize("kind", ("typed_dict", "dataclass"))
def test_plain_structure_uses_factory_json_config(kind):
    if kind == "typed_dict":

        class Record(TypedDict):
            value: bytes
    else:

        @dataclass
        class Record:
            value: bytes

    Record.__pydantic_config__ = {"ser_json_bytes": "hex"}
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=Record)

    assert factory.encode(serializer.response({"value": b"ab"})) == b'{"value":"YWI="}'
    schema = serializer.get_response_schema()
    assert resolve_root(schema)["properties"]["value"] == {
        "type": "string",
        "format": "base64url",
        "title": "Value",
    }


@pytest.mark.parametrize("wrapped", (True, False))
def test_bytes_response_describes_configured_encoding(wrapped):
    factory = PydanticSerializer(
        pydantic_config={"ser_json_bytes": "base64"}, use_fastdepends_errors=wrapped
    )
    serializer = factory(name="handler", options=[], response_type=list[bytes])

    assert factory.encode(serializer.response([b"ab"])) == b'["YWI="]'
    assert serializer.get_response_schema() == {
        "type": "array",
        "items": {"type": "string", "format": "base64url"},
    }


@pytest.mark.parametrize(
    "annotation", (bytes, ResponseBytes, bytes | None, ResponseBytes | None)
)
def test_root_bytes_response_preserves_raw_encoding(annotation):
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=annotation)

    assert factory.encode(serializer.response(b"\xff")) == b"\xff"
    schema = serializer.get_response_schema()
    root = resolve_root(schema)
    if "anyOf" in root:
        assert root["anyOf"][1] == {"type": "null"}
        root = root["anyOf"][0]
        assert factory.encode(serializer.response(None)) == b"null"
    root = resolve_part(schema, root)
    assert root == {
        "type": "string",
        "format": "binary",
    }


@pytest.mark.parametrize("nested_first", (True, False))
def test_bytes_alias_has_distinct_root_and_nested_formats(nested_first):
    annotation = (
        list[ResponseBytes] | ResponseBytes
        if nested_first
        else ResponseBytes | list[ResponseBytes]
    )
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=annotation)

    assert factory.encode(serializer.response(b"\xff")) == b"\xff"
    assert factory.encode(serializer.response([b"\xff"])) == b'["_w=="]'
    schema = serializer.get_response_schema()
    root = schema["anyOf"][1 if nested_first else 0]
    nested = schema["anyOf"][0 if nested_first else 1]["items"]
    root = resolve_part(schema, root)
    assert root == {"type": "string", "format": "binary"}
    assert resolve_root({**schema, **nested}) == {
        "type": "string",
        "format": "base64url",
    }


def test_recursive_bytes_alias_preserves_nested_json_encoding():
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=ByteTree)

    assert factory.encode(serializer.response(b"\xff")) == b"\xff"
    assert factory.encode(serializer.response([b"\xff", [b"ab"]])) == b'["_w==",["YWI="]]'
    schema = serializer.get_response_schema()
    root = resolve_root(schema)
    raw = root["anyOf"][0]
    raw = resolve_part(schema, raw)
    assert raw == {"type": "string", "format": "binary"}
    nested = resolve_root({**schema, **root["anyOf"][1]["items"]})
    assert nested["anyOf"][0] == {"type": "string", "format": "base64url"}
    assert resolve_root({**schema, **nested["anyOf"][1]["items"]}) == nested


def test_recursive_root_bytes_alias_keeps_raw_format():
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=ByteCycle)

    assert factory.encode(serializer.response(b"\xff")) == b"\xff"
    schema = serializer.get_response_schema()
    root = resolve_root(schema)
    assert root == {
        "anyOf": [
            {"type": "string", "format": "binary"},
            {"$ref": schema["$ref"]},
        ],
    }


def test_root_bytes_response_preserves_constraints():
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(
        name="handler",
        options=[],
        response_type=Annotated[bytes, Field(min_length=1, max_length=4)],
    )

    assert factory.encode(serializer.response(b"\xff")) == b"\xff"
    assert serializer.get_response_schema() == {
        "type": "string",
        "format": "binary",
        "minLength": 1,
        "maxLength": 4,
    }


@pytest.mark.parametrize(
    "wrapper",
    (
        "before",
        "after",
        "wrap",
        "default",
        "json",
        "custom_error",
        "chain",
        "json_or_python",
        "lax_or_strict",
    ),
)
def test_wrapped_bytes_response_preserves_root_and_nested_formats(wrapper):
    value = b"ab"
    if wrapper == "before":
        annotation = Annotated[bytes, BeforeValidator(lambda value: value)]
    elif wrapper == "after":
        annotation = Annotated[bytes, AfterValidator(lambda value: value)]
    elif wrapper == "wrap":
        annotation = Annotated[
            bytes, WrapValidator(lambda value, handler: handler(value))
        ]
    elif wrapper == "default":
        annotation = Annotated[bytes, Field(default=b"ab")]
    elif wrapper == "json":
        annotation = Json[bytes]
        value = '"ab"'
    else:

        class CustomBytes:
            @classmethod
            def __get_pydantic_core_schema__(cls, source, handler):
                inner = core_schema.bytes_schema()
                if wrapper == "custom_error":
                    return core_schema.custom_error_schema(
                        inner, "invalid_bytes", custom_error_message="Invalid bytes"
                    )
                if wrapper == "chain":
                    return core_schema.chain_schema([inner, inner])
                if wrapper == "json_or_python":
                    return core_schema.json_or_python_schema(inner, inner)
                return core_schema.lax_or_strict_schema(inner, inner)

        annotation = CustomBytes

    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    root = factory(name="handler", options=[], response_type=annotation)
    nested = factory(name="handler", options=[], response_type=list[annotation])

    assert factory.encode(root.response(value)) == b"ab"
    assert factory.encode(nested.response([value])) == b'["YWI="]'
    assert root.get_response_schema() == IsPartialDict(type="string", format="binary")
    assert nested.get_response_schema()["items"] == IsPartialDict(
        type="string", format="base64url"
    )


@pytest.mark.parametrize("annotation", (Json, Json[Any]))
def test_untyped_json_response_schema(annotation):
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=annotation)

    assert factory.encode(serializer.response('{"value":12}')) == b'{"value":12}'
    assert serializer.get_response_schema() == {}


def test_tagged_union_bytes_response_preserves_root_format():
    annotation = Annotated[
        Annotated[bytes, Tag("raw")] | Annotated[list[bytes], Tag("nested")],
        Discriminator(lambda value: "raw" if isinstance(value, bytes) else "nested"),
    ]
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=annotation)

    assert factory.encode(serializer.response(b"\xff")) == b"\xff"
    assert factory.encode(serializer.response([b"\xff"])) == b'["_w=="]'
    assert serializer.get_response_schema() == {
        "oneOf": [
            {"type": "string", "format": "binary"},
            {"type": "array", "items": {"type": "string", "format": "base64url"}},
        ],
    }


def test_labeled_union_bytes_response_preserves_root_format():
    class BytesOrList:
        @classmethod
        def __get_pydantic_core_schema__(cls, source, handler):
            return core_schema.union_schema(
                [
                    (core_schema.bytes_schema(), "raw"),
                    (core_schema.list_schema(core_schema.bytes_schema()), "nested"),
                ]
            )

    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=BytesOrList)

    assert factory.encode(serializer.response(b"\xff")) == b"\xff"
    assert factory.encode(serializer.response([b"\xff"])) == b'["_w=="]'
    assert serializer.get_response_schema() == {
        "anyOf": [
            {"type": "string", "format": "binary"},
            {"type": "array", "items": {"type": "string", "format": "base64url"}},
        ],
    }


def test_chained_text_response_schema_is_unchanged():
    class Text:
        @classmethod
        def __get_pydantic_core_schema__(cls, source, handler):
            return core_schema.chain_schema(
                [core_schema.str_schema(), core_schema.str_schema()]
            )

    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=Text)

    assert serializer.response("ab") == "ab"
    assert factory.encode(serializer.response("ab")) == b'"ab"'
    assert serializer.get_response_schema() == {"type": "string"}


@pytest.mark.parametrize("annotation", (str, bytes))
def test_response_preserves_explicit_json_schema_format(annotation):
    response_type = Annotated[
        annotation,
        Field(json_schema_extra={"format": "custom", "description": "Payload"}),
    ]
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(name="handler", options=[], response_type=response_type)

    assert factory.encode(serializer.response("ab")) == (
        b"ab" if annotation is bytes else b'"ab"'
    )
    assert serializer.get_response_schema() == {
        "type": "string",
        "format": "custom",
        "description": "Payload",
    }


def test_bytes_response_preserves_constraints():
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    serializer = factory(
        name="handler",
        options=[],
        response_type=list[Annotated[bytes, Field(min_length=1, max_length=4)]],
    )

    assert serializer.get_response_schema()["items"] == {
        "type": "string",
        "format": "base64url",
        "minLength": 1,
        "maxLength": 4,
    }
    assert factory.encode(serializer.response([b"ab"])) == b'["YWI="]'


def test_bytes_response_preserves_model_encoding_config():
    class Result(BaseModel):
        model_config = {"ser_json_bytes": "base64"}
        value: bytes

    serializer = PydanticSerializer()(name="handler", options=[], response_type=Result)

    assert PydanticSerializer.encode(serializer.response({"value": b"ab"})) == (
        b'{"value":"YWI="}'
    )
    assert serializer.get_response_schema() == Result.model_json_schema(
        mode="serialization"
    )


@pytest.mark.parametrize(
    "annotation, value, config",
    [
        (date, date(2026, 1, 1), {"ser_json_temporal": "seconds"}),
        (time, time(12, 30), {"ser_json_temporal": "seconds"}),
        (datetime, datetime(2026, 1, 1), {"ser_json_temporal": "seconds"}),
        (timedelta, timedelta(seconds=90), {"ser_json_timedelta": "float"}),
    ],
)
def test_temporal_response_preserves_model_encoding_config(annotation, value, config):
    class Result(BaseModel):
        model_config = config
        value: annotation

    serializer = PydanticSerializer()(name="handler", options=[], response_type=Result)
    data = {"value": value}
    result = serializer.response(data)

    assert (
        PydanticSerializer.encode(result)
        == Result.model_validate(data).model_dump_json().encode()
    )
    assert serializer.get_response_schema() == Result.model_json_schema(
        mode="serialization"
    )
