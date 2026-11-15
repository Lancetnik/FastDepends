from inspect import Parameter
from typing import Annotated, Any

import msgspec
import pytest

from fast_depends import Depends, Provider
from fast_depends.core import build_call_model
from fast_depends.exceptions import ValidationError
from fast_depends.library import CustomField
from fast_depends.library.serializer import OptionItem, Serializer
from fast_depends.msgspec import MsgSpecSerializer


class User(msgspec.Struct):
    user_id: Annotated[int, msgspec.Meta(gt=0)]


@pytest.mark.parametrize("wrapped", (False, True))
@pytest.mark.parametrize("embed", (False, True))
def test_prepared_decoder_preserves_alias_constraints_and_python_names(
    wrapped: bool, embed: bool
) -> None:
    serializer = MsgSpecSerializer(use_fastdepends_errors=wrapped)(
        name="Input",
        options=[OptionItem("user", User, default_value=msgspec.field(name="external"))],
        response_type=Parameter.empty,
    )
    decode = serializer.get_json_decoder(embed=embed)
    assert decode is not None
    data = b'{"user_id":"42"}' if embed else b'{"external":{"user_id":"42"}}'
    assert decode(data) == {"user": User(42)}
    bad = b'{"user_id":0}' if embed else b'{"external":{"user_id":0}}'
    expected = ValidationError if wrapped else msgspec.ValidationError
    with pytest.raises(expected):
        decode(bad)


def test_decoder_is_prepared_once(monkeypatch: pytest.MonkeyPatch) -> None:
    serializer = MsgSpecSerializer()(
        name="Input", options=[OptionItem("value", int)], response_type=Parameter.empty
    )
    decoder_type = msgspec.json.Decoder
    prepared = []

    def create(**kwargs: Any) -> Any:
        prepared.append(kwargs["type"])
        return decoder_type(**kwargs)

    monkeypatch.setattr(msgspec.json, "Decoder", create)
    decode = serializer.get_json_decoder(embed=True)
    assert decode is not None
    assert [decode(b"41"), decode(b"42")] == [{"value": 41}, {"value": 42}]
    assert prepared == [int]


def test_json_call_validates_custom_input_once_and_keeps_response_validation() -> None:
    class Token:
        def __init__(self, value: int):
            self.value = value

    seen = []

    def hook(expected: type, value: Any) -> Token:
        assert expected is Token and isinstance(value, int)
        seen.append(value)
        return Token(value)

    def handler(value: Token) -> int:
        result: Any = str(value.value + 1)
        return result

    model = build_call_model(
        handler,
        serializer_cls=MsgSpecSerializer(dec_hook=hook),
        dependency_provider=Provider(),
    )
    invoke = model.prepare_json_call(embed=True)
    assert invoke is not None
    assert invoke(b"41") == 42
    assert seen == [41]


@pytest.mark.anyio
async def test_async_json_call_and_independent_bindings() -> None:
    async def handler(value: int) -> int:
        return value + 1

    model = build_call_model(
        handler, serializer_cls=MsgSpecSerializer(), dependency_provider=Provider()
    )
    embedded = model.prepare_json_call(embed=True)
    object_call = model.prepare_json_call()
    assert embedded is not None and object_call is not None
    assert await embedded(b"41") == 42
    assert await object_call(b'{"value":42}') == 43
    assert await embedded(b"43") == 44


def test_multi_parameter_json_call() -> None:
    def handler(a: int, *, b: int = 2) -> int:
        return a + b

    model = build_call_model(
        handler, serializer_cls=MsgSpecSerializer(), dependency_provider=Provider()
    )
    invoke = model.prepare_json_call()
    assert invoke is not None
    assert invoke(b'{"a":"40"}') == 42
    assert model.prepare_json_call(embed=True) is None


def test_json_call_retains_backend_errors() -> None:
    def handler(value: int) -> None:
        raise AssertionError("handler must not run")

    model = build_call_model(
        handler, serializer_cls=MsgSpecSerializer(), dependency_provider=Provider()
    )
    invoke = model.prepare_json_call(embed=True)
    assert invoke is not None
    with pytest.raises(ValidationError):
        invoke(b'"invalid"')
    with pytest.raises(msgspec.DecodeError):
        invoke(b"?")
    with pytest.raises(msgspec.DecodeError):
        invoke(b'1,"injected":2')


@pytest.mark.parametrize("data", (b"NaN", b"Infinity", b"1e400"))
def test_native_json_number_limits(data: bytes) -> None:
    def handler(value: float) -> float:
        return value

    model = build_call_model(
        handler,
        serializer_cls=MsgSpecSerializer(use_fastdepends_errors=False),
        dependency_provider=Provider(),
    )
    invoke = model.prepare_json_call(embed=True)
    assert invoke is not None
    with pytest.raises(msgspec.DecodeError):
        invoke(data)


def test_legacy_serializer_without_json_capability_keeps_object_path() -> None:
    def handler(value: int) -> int:
        return value

    model = build_call_model(
        handler, serializer_cls=MsgSpecSerializer(), dependency_provider=Provider()
    )

    class Legacy:
        pass

    old: Any = Legacy()
    model.serializer = old
    assert model.prepare_json_call() is None


def test_object_only_serializers_keep_object_path() -> None:
    class ObjectOnly(Serializer):
        def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
            return call_kwargs

    def handler(value: int) -> int:
        return value

    factories: tuple[Any, ...] = (None, ObjectOnly)
    for factory in factories:
        model = build_call_model(
            handler, serializer_cls=factory, dependency_provider=Provider()
        )
        assert model.prepare_json_call() is None


def test_native_hooks_follow_repeated_keys() -> None:
    class Token:
        def __init__(self, value: int):
            self.value = value

    seen: list[int] = []

    def hook(expected: type, value: Any) -> Token:
        assert expected is Token
        seen.append(value)
        return Token(value)

    def handler(token: Token) -> int:
        return token.value

    model = build_call_model(
        handler,
        serializer_cls=MsgSpecSerializer(dec_hook=hook),
        dependency_provider=Provider(),
    )
    invoke = model.prepare_json_call()
    assert invoke is not None
    assert invoke(b'{"token":1,"token":2}') == 2
    assert seen == [1, 2]


def test_unsupported_call_shapes_keep_object_solving() -> None:
    class Field(CustomField):
        def use(self, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError("preparation must not resolve fields")

    def dependency(value: int) -> int:
        return value

    def dependant(value: int = Depends(dependency)) -> int:
        return value

    def custom(value: int = Field()) -> int:
        return value

    def varargs(*values: int) -> None: ...
    def kwargs(**values: int) -> None: ...
    def positional(value: int, /) -> None: ...
    def generator(value: int):
        yield value

    for handler in (dependant, custom, varargs, kwargs, positional, generator):
        model = build_call_model(
            handler, serializer_cls=MsgSpecSerializer(), dependency_provider=Provider()
        )
        assert model.prepare_json_call() is None

    model = build_call_model(
        dependency,
        serializer_cls=MsgSpecSerializer(),
        extra_dependencies=[Depends(dependency)],
        dependency_provider=Provider(),
    )
    assert model.prepare_json_call() is None
