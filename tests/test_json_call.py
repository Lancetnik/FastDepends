import json
from typing import Any

import anyio
import pytest

from fast_depends import Depends, Provider
from fast_depends.core import build_call_model
from fast_depends.library import CustomField


@pytest.mark.parametrize(
    "data",
    (
        pytest.param(b'{"a":40,"b":2}', id="object"),
        pytest.param(b"[40,2]", id="array"),
    ),
)
def test_json_argument_binding(data: bytes, provider: Provider) -> None:
    def handler(a: int, b: int) -> int:
        return a + b

    invoke = build_call_model(handler, dependency_provider=provider).prepare_json_call()
    assert invoke is not None
    assert invoke(data) == 42
    with pytest.raises(ValueError, match="object or sequence"):
        invoke(b"42")


def test_json_strings_require_embedding(provider: Provider) -> None:
    def handler(a: str, b: str = "") -> str:
        return a + b

    model = build_call_model(handler, dependency_provider=provider)
    invoke = model.prepare_json_call()
    assert invoke is not None
    with pytest.raises(ValueError, match="object or sequence"):
        invoke(b'"42"')

    embedded = model.prepare_json_call(embed=True)
    assert embedded is not None
    assert embedded(b'"42"') == "42"


@pytest.mark.anyio
async def test_async_json_strings_require_embedding(provider: Provider) -> None:
    async def handler(a: str, b: str = "") -> str:
        return a + b

    model = build_call_model(handler, dependency_provider=provider)
    invoke = model.prepare_json_call()
    assert invoke is not None
    with pytest.raises(ValueError, match="object or sequence"):
        await invoke(b'"42"')

    embedded = model.prepare_json_call(embed=True)
    assert embedded is not None
    assert await embedded(b'"42"') == "42"


def test_supplied_arguments_keep_dependency_precedence(provider: Provider) -> None:
    def dependency() -> int:
        raise AssertionError("a supplied dependency result must take precedence")

    def handler(a: int, b: int, result: int = Depends(dependency)) -> int:
        return a + b + result

    invoke = build_call_model(handler, dependency_provider=provider).prepare_json_call()
    assert invoke is not None
    assert invoke(b'{"a":1,"b":2,"result":40}', result=99) == 43


def test_embedded_keywords_override_positional_body(provider: Provider) -> None:
    def handler(value: int) -> int:
        return value

    invoke = build_call_model(handler, dependency_provider=provider).prepare_json_call(
        embed=True
    )
    assert invoke is not None
    assert invoke(b"41", value=42) == 42


def test_repeated_dependencies_share_mutable_input(provider: Provider) -> None:
    def dependency(payload: Any) -> int:
        payload["count"] += 1
        return payload["count"]

    def handler(
        a: int = Depends(dependency, use_cache=False),
        b: int = Depends(dependency, use_cache=False),
    ) -> tuple[int, int]:
        return a, b

    invoke = build_call_model(handler, dependency_provider=provider).prepare_json_call(
        embed=True
    )
    assert invoke is not None
    assert invoke(b'{"count":0}') == (1, 2)


def test_extra_dependency_runs_before_handler(provider: Provider) -> None:
    def dependency(payload: Any) -> None:
        payload["count"] += 1

    def handler(payload: Any) -> int:
        return payload["count"]

    invoke = build_call_model(
        handler, dependency_provider=provider, extra_dependencies=[Depends(dependency)]
    ).prepare_json_call(embed=True)
    assert invoke is not None
    assert invoke(b'{"count":41}') == 42


def test_custom_field_uses_caller_owned_body(provider: Provider) -> None:
    body = {"count": 1}
    events = []

    class Field(CustomField):
        def use(self, **kwargs: Any) -> dict[str, Any]:
            kwargs = super().use(**kwargs)
            events.append("field")
            assert kwargs["payload"] is body
            body["count"] = 41
            kwargs["extra"] = 1
            return kwargs

    def handler(payload: Any, extra: int = Field()) -> int:
        events.append("handler")
        return payload["count"] + extra

    def load():
        events.append("load")
        return (body,), {}

    invoke = build_call_model(handler, dependency_provider=provider).prepare_json_call(
        embed=True
    )
    assert invoke is not None
    assert invoke(b'{"count":0}', load_arguments=load) == 42
    assert events == ["load", "field", "handler"]
    assert body == {"count": 41}


@pytest.mark.anyio
async def test_async_fields_and_dependency_cleanup(provider: Provider) -> None:
    events = []

    async def dependency():
        events.append("enter")
        try:
            yield 1
        finally:
            events.append("exit")

    class Field(CustomField):
        def __init__(self):
            super().__init__()
            self.field = True

        async def use_field(self, kwargs: dict[str, Any]) -> None:
            events.append("field")
            kwargs["extra"] = 2

    async def handler(
        value: int, result: int = Depends(dependency), extra: int = Field()
    ):
        events.append("handler")
        return value + result + extra

    async def load():
        events.append("load")
        return (40,), {}

    invoke = build_call_model(handler, dependency_provider=provider).prepare_json_call(
        embed=True
    )
    assert invoke is not None
    assert await invoke(b"0", load_arguments=load) == 43
    assert events == ["load", "enter", "field", "handler", "exit"]


@pytest.mark.anyio
async def test_json_cancellation_closes_dependencies(provider: Provider) -> None:
    started = anyio.Event()
    events = []

    async def dependency():
        events.append("enter")
        try:
            yield 1
        finally:
            events.append("exit")

    async def handler(result: int = Depends(dependency)) -> None:
        assert result == 1
        started.set()
        await anyio.sleep_forever()

    invoke = build_call_model(handler, dependency_provider=provider).prepare_json_call(
        embed=True
    )
    assert invoke is not None
    with anyio.fail_after(2):
        async with anyio.create_task_group() as group:
            group.start_soon(invoke, b"null")
            await started.wait()
            group.cancel_scope.cancel()
    assert events == ["enter", "exit"]


def test_recursive_override_does_not_loop_during_preparation(provider: Provider) -> None:
    def dependency() -> None: ...

    def replacement(result: Any = Depends(dependency)) -> None: ...

    def handler(result: Any = Depends(dependency)) -> None: ...

    model = build_call_model(handler, dependency_provider=provider)
    provider.override(dependency, replacement)
    assert model.prepare_json_call(embed=True) is not None


def test_syntax_errors_precede_dependencies(provider: Provider) -> None:
    def dependency() -> None:
        raise AssertionError("invalid JSON must fail before dependencies")

    def handler(value: Any, result: Any = Depends(dependency)) -> None: ...

    invoke = build_call_model(handler, dependency_provider=provider).prepare_json_call(
        embed=True
    )
    assert invoke is not None
    with pytest.raises(json.JSONDecodeError):
        invoke(b"?")
