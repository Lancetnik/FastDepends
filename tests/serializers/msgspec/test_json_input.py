from collections.abc import Callable
from functools import partial
from inspect import Parameter
from typing import Annotated, Any

import msgspec
import pytest

from fast_depends import Depends, Provider, inject
from fast_depends.core import CallModel, build_call_model
from fast_depends.exceptions import ValidationError
from fast_depends.library.serializer import OptionItem, Serializer
from fast_depends.msgspec import MsgSpecSerializer


class User(msgspec.Struct):
    user_id: Annotated[int, msgspec.Meta(gt=0)]


class Token:
    def __init__(self, value: int):
        self.value = value


class Loader:
    def __bool__(self) -> bool:
        raise AssertionError("argument loaders must not be truth-tested")

    def __call__(self) -> tuple[tuple[int, ...], dict[str, Any]]:
        return (42,), {}


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
    assert await embedded(None, load_arguments=Loader()) == 43
    with pytest.raises(ValueError, match="object or sequence"):
        await object_call(b'"42"')


def test_multi_parameter_json_call(build_model: Callable[..., CallModel]) -> None:
    def handler(a: int, *, b: int = 2) -> int:
        return a + b

    model = build_model(handler)
    invoke = model.prepare_json_call()
    assert invoke is not None
    assert invoke(b'{"a":"40"}') == 42
    with pytest.raises(ValueError, match="object or sequence"):
        invoke(b'"42"')
    embedded = model.prepare_json_call(embed=True)
    assert embedded is not None
    assert embedded(b"40") == 42


@pytest.mark.anyio
async def test_async_dependency_receives_native_body(
    build_model: Callable[..., CallModel],
) -> None:
    async def dependency(value: User) -> int:
        return value.user_id

    async def handler(result: int = Depends(dependency)) -> int:
        return result + 1

    def forbidden() -> Any:
        raise AssertionError("native input must not use the object loader")

    invoke = build_model(handler).prepare_json_call(embed=True)
    assert invoke is not None
    assert await invoke(b'{"user_id":41}', load_arguments=forbidden) == 42


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


def test_cached_arguments_bypass_native_decoding(
    build_model: Callable[..., CallModel],
) -> None:
    def handler(value: int) -> int:
        return value

    invoke = build_model(handler).prepare_json_call(embed=True)
    assert invoke is not None
    assert invoke(None, load_arguments=Loader()) == 42
    with pytest.raises(ValueError, match="load_arguments is required"):
        invoke(None)


def test_legacy_serializer_uses_normal_solving(
    build_model: Callable[..., CallModel],
) -> None:
    def handler(value: int) -> int:
        return value

    class Legacy:
        def __call__(self, kwargs: dict[str, Any]) -> dict[str, Any]:
            return kwargs

        def response(self, value: Any) -> Any:
            return value

    model = build_model(handler)
    old: Any = Legacy()
    model.serializer = old
    invoke = model.prepare_json_call()
    assert invoke is not None
    assert invoke(b'{"value":41}') == 41


@pytest.mark.parametrize("factory", (None, ObjectOnly))
def test_object_only_serializers_keep_object_path(
    factory: Any, build_model: Callable[..., CallModel]
) -> None:
    def handler(value: int) -> int:
        return value

    model = build_model(handler, serializer_cls=factory)
    invoke = model.prepare_json_call()
    assert invoke is not None
    assert invoke(b'{"value":41}') == 41
    assert inject(serializer_cls=factory)(handler, model=model)(41) == 41


@pytest.mark.parametrize(
    "prefix", (pytest.param(b"", id="plain"), pytest.param(b" \t\r\n", id="whitespace"))
)
def test_native_hooks_follow_repeated_keys(
    prefix: bytes, build_model: Callable[..., CallModel]
) -> None:
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
    assert invoke(prefix + b'{"token":1,"token":2}') == 2
    assert seen == [1, 2]


def test_json_whitespace_preserves_native_validation(
    build_model: Callable[..., CallModel],
) -> None:
    def handler(value: float) -> None:
        raise AssertionError("invalid input must not reach the handler")

    invoke = build_model(handler).prepare_json_call()
    assert invoke is not None
    with pytest.raises(ValidationError):
        invoke(b' \t\r\n{"value":1e400}')


@pytest.mark.anyio
async def test_async_json_whitespace_preserves_native_validation(
    build_model: Callable[..., CallModel],
) -> None:
    async def handler(value: float) -> None:
        raise AssertionError("invalid input must not reach the handler")

    invoke = build_model(handler).prepare_json_call()
    assert invoke is not None
    with pytest.raises(ValidationError):
        await invoke(b' \t\r\n{"value":1e400}')


def test_unsupported_call_shapes_return_none(
    build_model: Callable[..., CallModel],
) -> None:
    def varargs(*values: int) -> None: ...
    def kwargs(**values: int) -> None: ...
    def positional(value: int, /) -> None: ...

    for handler in (varargs, kwargs, positional):
        model = build_model(handler)
        assert model.prepare_json_call() is None


def test_generator_keeps_object_solving(build_model: Callable[..., CallModel]) -> None:
    def handler(value: int):
        yield value

    model = build_model(handler)
    assert model.prepare_json_call() is None
    assert list(inject(serializer_cls=MsgSpecSerializer())(handler, model=model)(41)) == [
        41
    ]


def test_native_dependency_body_and_injected_result_validation(
    build_model: Callable[..., CallModel], monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = []

    def hook(expected: type, value: Any) -> Token:
        assert expected is Token
        seen.append(value)
        return Token(value)

    def dependency(value: Token) -> str:
        return str(value.value)

    def handler(result: int = Depends(dependency)) -> int:
        return result + 1

    model = build_model(handler, serializer_cls=MsgSpecSerializer(dec_hook=hook))
    invoke = model.prepare_json_call(embed=True)
    assert invoke is not None

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("native input must not use the object loader")

    monkeypatch.setattr("fast_depends.core.json.json.loads", forbidden)
    assert invoke(b"41", load_arguments=forbidden) == 42
    assert invoke(b"42", load_arguments=forbidden) == 43
    assert seen == [41, 42]


def test_dependency_runs_before_body_validation(
    build_model: Callable[..., CallModel],
) -> None:
    seen = []

    def dependency() -> int:
        seen.append("dependency")
        return 1

    def handler(value: int, result: int = Depends(dependency)) -> int:
        raise AssertionError("invalid input must fail before the handler")

    invoke = build_model(handler).prepare_json_call(embed=True)
    assert invoke is not None
    with pytest.raises(ValidationError):
        invoke(b'"invalid"')
    assert seen == ["dependency"]


def test_prepared_dependency_respects_provider_changes(
    build_model: Callable[..., CallModel], provider: Provider
) -> None:
    def dependency(value: int) -> int:
        return value + 1

    def replacement(value: str) -> str:
        return value.upper()

    def handler(result: Any = Depends(dependency, cast=False)) -> Any:
        return result

    model = build_model(handler)
    invoke = model.prepare_json_call(embed=True)
    assert invoke is not None
    assert invoke(b"41") == 42
    with provider.scope(dependency, replacement):
        assert invoke(b'"replacement"') == "REPLACEMENT"
    assert invoke(b"41") == 42

    override = Provider()
    override.override(dependency, replacement)
    assert invoke(b'"overlay"', dependency_provider=override) == "OVERLAY"


def test_variadic_dependency_keeps_object_solving(
    build_model: Callable[..., CallModel],
) -> None:
    def dependency(*values: tuple[int, ...]) -> int:
        return sum(values)

    def handler(result: int = Depends(dependency)) -> int:
        return result

    invoke = build_model(handler).prepare_json_call(embed=True)
    assert invoke is not None
    assert invoke(b"42") == 42
