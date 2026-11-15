from collections.abc import Callable
from functools import partial
from inspect import Parameter
from typing import Annotated, Any

import msgspec
import pytest

from fast_depends import Depends, Provider, inject
from fast_depends.core import CallModel, build_call_model
from fast_depends.exceptions import ValidationError
from fast_depends.library import CustomField
from fast_depends.library.serializer import OptionItem, Serializer
from fast_depends.msgspec import MsgSpecSerializer


class User(msgspec.Struct):
    user_id: Annotated[int, msgspec.Meta(gt=0)]


class Token:
    def __init__(self, value: int):
        self.value = value


class ObjectOnly(Serializer):
    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        return call_kwargs


@pytest.fixture
def build_model(provider: Provider) -> Callable[..., CallModel]:
    return partial(
        build_call_model, dependency_provider=provider, serializer_cls=MsgSpecSerializer()
    )


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


def test_hook_runs_once_and_response_is_validated(
    build_model: Callable[..., CallModel],
) -> None:
    seen = []

    def hook(expected: type, value: Any) -> Token:
        assert expected is Token and isinstance(value, int)
        seen.append(value)
        return Token(value)

    def handler(value: Token) -> int:
        result: Any = str(value.value + 1)
        return result

    model = build_model(handler, serializer_cls=MsgSpecSerializer(dec_hook=hook))
    invoke = model.prepare_json_call(embed=True)
    assert invoke is not None
    assert invoke(b"41") == 42
    assert seen == [41]


@pytest.mark.anyio
async def test_async_json_call_and_independent_bindings(
    build_model: Callable[..., CallModel],
) -> None:
    async def handler(value: int) -> int:
        return value + 1

    model = build_model(handler)
    embedded = model.prepare_json_call(embed=True)
    object_call = model.prepare_json_call()
    assert embedded is not None and object_call is not None
    assert await embedded(b"41") == 42
    assert await object_call(b'{"value":42}') == 43
    assert await embedded(b"43") == 44


def test_multi_parameter_json_call(build_model: Callable[..., CallModel]) -> None:
    def handler(a: int, *, b: int = 2) -> int:
        return a + b

    model = build_model(handler)
    invoke = model.prepare_json_call()
    assert invoke is not None
    assert invoke(b'{"a":"40"}') == 42
    assert model.prepare_json_call(embed=True) is None


@pytest.mark.parametrize(
    ("data", "error"),
    (
        (b'"invalid"', ValidationError),
        (b"?", msgspec.DecodeError),
        (b'1,"injected":2', msgspec.DecodeError),
        (b"NaN", msgspec.DecodeError),
        (b"Infinity", msgspec.DecodeError),
        (b"1e400", ValidationError),
    ),
)
def test_json_call_retains_validation_and_decode_errors(
    data: bytes, error: type[Exception], build_model: Callable[..., CallModel]
) -> None:
    def handler(value: float) -> None:
        raise AssertionError("invalid input must not reach the handler")

    model = build_model(handler)
    invoke = model.prepare_json_call(embed=True)
    assert invoke is not None
    with pytest.raises(error):
        invoke(data)


def test_legacy_serializer_without_json_capability_returns_none(
    build_model: Callable[..., CallModel],
) -> None:
    def handler(value: int) -> int:
        raise AssertionError("preparation must not invoke the handler")

    model = build_model(handler)

    old: Any = object()
    model.serializer = old
    assert model.prepare_json_call() is None


@pytest.mark.parametrize("factory", (None, ObjectOnly))
def test_object_only_serializers_keep_object_path(
    factory: Any, build_model: Callable[..., CallModel]
) -> None:
    def handler(value: int) -> int:
        return value

    model = build_model(handler, serializer_cls=factory)
    assert model.prepare_json_call() is None
    assert inject(serializer_cls=factory)(handler, model=model)(41) == 41


def test_native_hooks_follow_repeated_keys(build_model: Callable[..., CallModel]) -> None:
    seen: list[int] = []

    def hook(expected: type, value: Any) -> Token:
        assert expected is Token
        seen.append(value)
        return Token(value)

    def handler(token: Token) -> int:
        return token.value

    model = build_model(handler, serializer_cls=MsgSpecSerializer(dec_hook=hook))
    invoke = model.prepare_json_call()
    assert invoke is not None
    assert invoke(b'{"token":1,"token":2}') == 2
    assert seen == [1, 2]


def test_unsupported_call_shapes_return_none(
    build_model: Callable[..., CallModel],
) -> None:
    class Field(CustomField):
        def use(self, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError("preparation must not resolve fields")

    def dependency(value: int) -> int:
        raise AssertionError("preparation must not resolve dependencies")

    def dependant(value: int = Depends(dependency)) -> int:
        raise AssertionError("preparation must not invoke the handler")

    def custom(value: int = Field()) -> int:
        raise AssertionError("preparation must not invoke the handler")

    def varargs(*values: int) -> None: ...
    def kwargs(**values: int) -> None: ...
    def positional(value: int, /) -> None: ...

    for handler in (dependant, custom, varargs, kwargs, positional):
        model = build_model(handler)
        assert model.prepare_json_call() is None

    model = build_model(dependency, extra_dependencies=[Depends(dependency)])
    assert model.prepare_json_call() is None


def test_generator_keeps_object_solving(build_model: Callable[..., CallModel]) -> None:
    def handler(value: int):
        yield value

    model = build_model(handler)
    assert model.prepare_json_call() is None
    assert list(inject(serializer_cls=MsgSpecSerializer())(handler, model=model)(41)) == [
        41
    ]
