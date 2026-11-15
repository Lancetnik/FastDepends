import inspect
from typing import Annotated, Any

import msgspec
import pytest

from fast_depends import Depends, Provider, inject
from fast_depends.core import build_call_model
from fast_depends.library import CustomField, SchemaField
from fast_depends.library.serializer import OptionItem
from fast_depends.msgspec import MsgSpecSerializer
from tests.serializers.test_schema import resolve_root


class Token:
    def __init__(self, value: str):
        self.value = value


class Envelope(msgspec.Struct, rename="camel", tag="envelope", omit_defaults=True):
    access_token: Annotated[Token, msgspec.Meta(description="Access token")]
    retry_count: Annotated[int, msgspec.Meta(ge=0)] = 0


def decode_token(type_: type, value: Any) -> Token:
    if type_ is Token:
        return value if isinstance(value, Token) else Token(value)
    raise NotImplementedError


def encode_token(value: Any) -> str:
    if isinstance(value, Token):
        return value.value
    raise NotImplementedError


def token_schema(type_: type) -> dict[str, Any]:
    if type_ is Token:
        return {"type": "string", "minLength": 1}
    raise NotImplementedError


@pytest.mark.parametrize("wrapped", (True, False))
@pytest.mark.parametrize("response_type", (Token, inspect.Parameter.empty))
@pytest.mark.parametrize("configured", (True, False))
def test_encoder_override_reaches_bound_serializer(wrapped, response_type, configured):
    class Factory(MsgSpecSerializer):
        def encode(self, value):
            return b"custom:" + value.value.encode()

    factory = Factory(wrapped, enc_hook=encode_token) if configured else Factory(wrapped)
    serializer = factory(name="handler", options=[], response_type=response_type)
    assert (
        serializer.encode(Token("one")) == factory.encode(Token("one")) == b"custom:one"
    )


@pytest.mark.parametrize("wrapped", (True, False))
@pytest.mark.parametrize("response_type", (Envelope, inspect.Parameter.empty))
def test_configured_encoder_preserves_struct_options(wrapped, response_type):
    factory = MsgSpecSerializer(wrapped, decode_token, enc_hook=encode_token)
    serializer = factory(name="handler", options=[], response_type=response_type)
    result = serializer.response(Envelope(Token("one")))
    assert isinstance(result.access_token, Token)
    assert (
        serializer.encode(result)
        == factory.encode(result)
        == (b'{"type":"envelope","accessToken":"one"}')
    )
    assert serializer.encode(b"raw") == factory.encode(b"raw") == b"raw"
    assert MsgSpecSerializer.encode(42) == b"42"
    with pytest.raises(TypeError):
        MsgSpecSerializer.encode(result)


@pytest.mark.parametrize("wrapped", (True, False))
def test_hooks_keep_validation_encoding_and_schema_separate(wrapped):
    events = []

    def decode(type_, value):
        events.append("decode")
        return decode_token(type_, value)

    def encode(value):
        events.append("encode")
        return encode_token(value)

    def schema(type_):
        events.append("schema")
        return token_schema(type_)

    factory = MsgSpecSerializer(wrapped, decode, enc_hook=encode, schema_hook=schema)

    def dependency(raw: Token) -> Token:
        events.append("dependency")
        return raw

    def handler(token: Token = Depends(dependency)) -> Token:
        events.append("handler")
        return token.value

    call = build_call_model(
        handler, dependency_provider=Provider(), serializer_cls=factory
    )
    assert events == []
    serializer = call.serializer
    assert serializer is not None
    schema_value = serializer.get_schema(resolve_refs=True)
    assert schema_value["properties"]["raw"] == token_schema(Token)
    assert serializer.get_response_schema() == token_schema(Token)
    assert set(events) == {"schema"}

    events.clear()
    handler = inject(serializer_cls=factory)(handler, model=call)
    result = handler(raw="one")
    assert isinstance(result, Token) and result.value == "one"
    assert events.count("dependency") == events.count("handler") == 1
    assert events.count("decode") >= 2
    assert set(events) == {"decode", "dependency", "handler"}
    events.clear()
    assert serializer.encode(result) == b'"one"'
    assert events == ["encode"]


def test_encoder_keeps_hook_state_and_factory_isolation():
    prefix = ["first:"]

    def encode(value):
        return prefix[0] + encode_token(value)

    factory = MsgSpecSerializer(enc_hook=encode)
    first = factory(name="first", options=[], response_type=Token)
    second = factory(name="second", options=[], response_type=inspect.Parameter.empty)
    other = MsgSpecSerializer(enc_hook=encode_token)(
        name="other", options=[], response_type=Token
    )
    assert first.encode(Token("one")) == b'"first:one"'
    prefix[0] = "next:"
    assert first.encode(Token("one")) == second.encode(Token("one")) == b'"next:one"'
    assert other.encode(Token("one")) == b'"one"'
    with pytest.raises(TypeError):
        MsgSpecSerializer()(name="default", options=[], response_type=Token).encode(
            Token("one")
        )


@pytest.mark.parametrize("operation", ("encode", "input_schema", "response_schema"))
def test_hook_errors_propagate(operation):
    error = RuntimeError("hook failure")

    def fail(value):
        raise error

    serializer = MsgSpecSerializer(enc_hook=fail, schema_hook=fail)(
        name="handler", options=[OptionItem("token", Token)], response_type=Token
    )
    with pytest.raises(RuntimeError) as caught:
        if operation == "encode":
            serializer.encode(Token("one"))
        elif operation == "input_schema":
            serializer.get_schema()
        else:
            serializer.get_response_schema()
    assert caught.value is error


def test_instance_encoder_override_is_retained():
    factory = MsgSpecSerializer(enc_hook=encode_token)
    factory.encode = lambda value: b"instance"
    serializer = factory(name="handler", options=[], response_type=Token)
    assert serializer.encode(Token("one")) == b"instance"


def test_static_encoder_override_is_retained():
    class Parent(MsgSpecSerializer):
        @staticmethod
        def encode(value):
            return b"static"

    class Child(Parent):
        pass

    serializer = Child(enc_hook=encode_token)(
        name="handler", options=[], response_type=Token
    )
    assert serializer.encode(Token("one")) == b"static"


@pytest.mark.parametrize(
    "path", ("standalone", "filtered", "dependency", "grouped", "response")
)
def test_schema_hook_preserves_nested_struct_metadata(path):
    result = {"type": "string", "minLength": 1}
    seen = []

    def schema(type_):
        seen.append(type_)
        assert type_ is Token
        return result

    class Header(CustomField):
        def get_schema(self, parameter):
            return SchemaField(
                parameter.field_name, parameter.field_type, source="headers"
            )

        def use(self, **kwargs):
            raise AssertionError("Custom field executed during schema generation")

    factory = MsgSpecSerializer(schema_hook=schema)
    if path in ("dependency", "grouped"):

        def dependency(payload: Envelope):
            raise AssertionError("Dependency executed during schema generation")

        if path == "dependency":

            def handler(value=Depends(dependency)):
                raise AssertionError("Handler executed during schema generation")
        else:

            def handler(payload: Annotated[Envelope, Header()]):
                raise AssertionError("Handler executed during schema generation")

        call = build_call_model(
            handler, dependency_provider=Provider(), serializer_cls=factory
        )
        serializer = call.serializer
        assert serializer is not None
    else:
        serializer = factory(
            name="handler",
            options=[OptionItem("payload", Envelope), OptionItem("unused", int)],
            response_type=Envelope,
        )
    assert seen == []
    for minimum in (1, 2):
        result["minLength"] = minimum
        if path == "response":
            document = serializer.get_response_schema()
            record = resolve_root(document)
        else:
            document = serializer.get_schema(
                exclude=("unused",) if path == "filtered" else (), resolve_refs=True
            )
            root = document["properties"]
            if path == "grouped":
                assert document["required"] == ["headers"]
                root = root["headers"]["properties"]
            if path == "filtered":
                assert "unused" not in root
            record = root["payload"]
        assert record["properties"]["accessToken"] == {
            "type": "string",
            "minLength": minimum,
            "description": "Access token",
        }
        assert record["properties"]["type"] == {"enum": ["envelope"]}
        assert record["properties"]["retryCount"] == {
            "type": "integer",
            "minimum": 0,
            "default": 0,
        }
        assert record["required"] == ["type", "accessToken"]
        assert result == {"type": "string", "minLength": minimum}
    assert seen and set(seen) == {Token}
