import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AsyncExitStack, ExitStack
from inspect import Parameter, isawaitable
from typing import TYPE_CHECKING, Any, NamedTuple

from fast_depends.utils import run_async

if TYPE_CHECKING:
    from .model import CallModel


Arguments = tuple[tuple[Any, ...], dict[str, Any]]
ArgumentLoader = Callable[[], Arguments | Awaitable[Arguments]]
JSONDecoder = Callable[[bytes], dict[str, Any]]


class JSONInput(dict[Callable[..., Any], Any]):
    __slots__ = ("model", "decoder", "data")

    def __init__(
        self,
        model: "CallModel",
        decoder: JSONDecoder,
        data: bytes,
    ) -> None:
        super().__init__()
        self.model = model
        self.decoder = decoder
        self.data = data


class JSONPlan(NamedTuple):
    models: tuple["CallModel", ...]
    decoder: JSONDecoder

    def is_current(self) -> bool:
        for parent, child in zip(self.models, self.models[1:], strict=False):
            key = next(iter(parent.dependencies.values()))
            if parent.dependency_provider.get_dependant(key) is not child:
                return False
        return True


def _native_plan(model: "CallModel", embed: bool) -> JSONPlan | None:
    chain = []
    while model not in chain:
        if (
            model.is_generator
            or model.custom_fields
            or model.extra_dependencies
            or any(
                p.kind
                in (
                    Parameter.POSITIONAL_ONLY,
                    Parameter.VAR_POSITIONAL,
                    Parameter.VAR_KEYWORD,
                )
                for p in model.params
            )
        ):
            return None
        chain.append(model)
        if not model.dependencies:
            prepare = getattr(model.serializer, "get_json_decoder", None)
            decoder = prepare(embed=embed) if prepare is not None else None
            return JSONPlan(tuple(chain), decoder) if decoder is not None else None
        # No user code precedes the body consumer in an embedded dependency chain.
        if not embed or model.params or len(model.dependencies) != 1:
            return None
        key = next(iter(model.dependencies.values()))
        model = model.dependency_provider.get_dependant(key)
    return None


def _load_arguments(data: bytes | None, embed: bool) -> Arguments:
    if data is None:
        raise ValueError("load_arguments is required without JSON bytes")
    value = json.loads(data)
    if embed:
        return (value,), {}
    if isinstance(value, Mapping):
        return (), dict(value)
    if isinstance(value, Sequence):
        return tuple(value), {}
    raise ValueError("JSON arguments must be an object or sequence")


def prepare_json_call(model: "CallModel", embed: bool) -> Callable[..., Any] | None:
    if (
        model.is_generator
        or model.args_name
        or model.kwargs_name
        or any(p.kind is Parameter.POSITIONAL_ONLY for p in model.params)
    ):
        return None

    plan = _native_plan(model, embed)
    direct = plan is not None and len(plan.models) == 1

    def native(data: bytes, kwargs: dict[str, Any]) -> JSONPlan | None:
        if (
            plan is not None
            and not kwargs
            and (embed or data.startswith(b"{"))
            and (direct or plan.is_current())
        ):
            return plan
        return None

    if model.is_async:

        async def async_invoke(
            data: bytes | None,
            /,
            *,
            load_arguments: ArgumentLoader | None = None,
            **kwargs: Any,
        ) -> Any:
            cache: dict[Callable[..., Any], Any]
            values: dict[str, Any]
            if data is not None and (prepared := native(data, kwargs)) is not None:
                if direct:
                    return model._cast_response(
                        await run_async(model.call, **prepared.decoder(data))
                    )
                cache = JSONInput(prepared.models[-1], prepared.decoder, data)
                args, values = (), {}
            else:
                loaded = (
                    load_arguments()
                    if load_arguments is not None
                    else _load_arguments(data, embed)
                )
                args, values = await loaded if isawaitable(loaded) else loaded
                cache = {}
            async with AsyncExitStack() as stack:
                return await model.asolve(
                    *args, stack=stack, cache_dependencies=cache, **(kwargs | values)
                )

        return async_invoke

    def invoke(
        data: bytes | None,
        /,
        *,
        load_arguments: Callable[[], Arguments] | None = None,
        **kwargs: Any,
    ) -> Any:
        cache: dict[Callable[..., Any], Any]
        values: dict[str, Any]
        if data is not None and (prepared := native(data, kwargs)) is not None:
            if direct:
                return model._cast_response(model.call(**prepared.decoder(data)))
            cache = JSONInput(prepared.models[-1], prepared.decoder, data)
            args, values = (), {}
        else:
            args, values = (
                load_arguments()
                if load_arguments is not None
                else _load_arguments(data, embed)
            )
            cache = {}
        with ExitStack() as stack:
            return model.solve(
                *args, stack=stack, cache_dependencies=cache, **(kwargs | values)
            )

    return invoke
