from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from contextlib import AsyncExitStack, ExitStack, aclosing, closing
from functools import partial, wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Protocol,
    TypeVar,
    Union,
    overload,
)

from typing_extensions import ParamSpec

from fast_depends.core import CallModel, build_call_model
from fast_depends.dependencies import Dependant, Provider
from fast_depends.library.serializer import SerializerProto

SerializerCls: Optional["SerializerProto"] = None

try:
    from fast_depends.pydantic import PydanticSerializer

    SerializerCls = PydanticSerializer()
except ImportError:
    pass

if SerializerCls is None:
    try:
        from fast_depends.msgspec import MsgSpecSerializer

        SerializerCls = MsgSpecSerializer()
    except ImportError:
        pass


P = ParamSpec("P")
T = TypeVar("T")

if TYPE_CHECKING:
    from fast_depends.library.serializer import SerializerProto

    class InjectWrapper(Protocol[P, T]):
        def __call__(
            self,
            func: Callable[P, T],
            model: CallModel | None = None,
        ) -> Callable[P, T]: ...


global_provider = Provider()


def Depends(
    dependency: Callable[..., Any],
    *,
    use_cache: bool = True,
    cast: bool = True,
    cast_result: bool = False,
) -> Any:
    return Dependant(
        dependency=dependency,
        use_cache=use_cache,
        cast=cast,
        cast_result=cast_result,
    )


def _identity_model(model: CallModel) -> CallModel:
    return model


@overload
def inject(
    func: Callable[P, T],
    *,
    cast: bool = True,
    cast_result: bool = True,
    extra_dependencies: Sequence["Dependant"] = (),
    dependency_provider: Optional["Provider"] = None,
    wrap_model: Callable[["CallModel"], "CallModel"] = _identity_model,
    serializer_cls: Optional["SerializerProto"] = SerializerCls,
    **call_extra: Any,
) -> Callable[P, T]: ...


@overload
def inject(
    func: None = None,
    *,
    cast: bool = True,
    cast_result: bool = True,
    extra_dependencies: Sequence["Dependant"] = (),
    dependency_provider: Optional["Provider"] = None,
    wrap_model: Callable[["CallModel"], "CallModel"] = _identity_model,
    serializer_cls: Optional["SerializerProto"] = SerializerCls,
    **call_extra: Any,
) -> "InjectWrapper[..., Any]": ...


def inject(
    func: Callable[P, T] | None = None,
    *,
    cast: bool = True,
    cast_result: bool = True,
    extra_dependencies: Sequence[Dependant] = (),
    dependency_provider: Optional["Provider"] = None,
    wrap_model: Callable[["CallModel"], "CallModel"] = _identity_model,
    serializer_cls: Optional["SerializerProto"] = SerializerCls,
    **call_extra: Any,
) -> Union[Callable[P, T], "InjectWrapper[P, T]"]:
    if dependency_provider is None:
        dependency_provider = global_provider

    if not cast:
        serializer_cls = None

    decorator: InjectWrapper[P, T] = _wrap_inject(
        dependency_provider=dependency_provider,
        wrap_model=wrap_model,
        extra_dependencies=extra_dependencies,
        serializer_cls=serializer_cls,
        cast_result=cast_result,
        **call_extra,
    )

    if func is None:
        return decorator
    return decorator(func)


def _wrap_inject(
    *,
    dependency_provider: "Provider",
    wrap_model: Callable[["CallModel"], "CallModel"],
    extra_dependencies: Sequence[Dependant],
    serializer_cls: Optional["SerializerProto"],
    cast_result: bool,
    **call_extra: Any,
) -> "InjectWrapper[P, T]":
    def func_wrapper(
        func: Callable[P, T],
        model: Optional["CallModel"] = None,
    ) -> Callable[P, T]:
        if model is None:
            real_model = wrap_model(
                build_call_model(
                    call=func,
                    extra_dependencies=extra_dependencies,
                    dependency_provider=dependency_provider,
                    serializer_cls=serializer_cls,
                    serialize_result=cast_result,
                    _prepare=wrap_model is _identity_model,
                )
            )
            if wrap_model is not _identity_model:
                real_model.prepare(force=True)
        else:
            real_model = model

        if real_model.is_async:
            injected_wrapper: Callable[P, T]

            if real_model.is_generator:
                injected_wrapper = partial(  # type: ignore[assignment]
                    solve_async_gen,
                    real_model,
                    call_extra,
                )

            else:

                async def injected_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:  # type: ignore[misc]
                    async with AsyncExitStack() as stack:
                        return await real_model.asolve(  # type: ignore[no-any-return]
                            stack=stack,
                            cache_dependencies={},
                            nested=False,
                            arguments=(args, kwargs),
                            context=call_extra,
                        )

                    raise AssertionError("unreachable")

        else:
            if real_model.is_generator:
                injected_wrapper = partial(  # type: ignore[assignment]
                    solve_gen,
                    real_model,
                    call_extra,
                )

            else:

                def injected_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                    with ExitStack() as stack:
                        return real_model.solve(  # type: ignore[no-any-return]
                            stack=stack,
                            cache_dependencies={},
                            nested=False,
                            arguments=(args, kwargs),
                            context=call_extra,
                        )

                    raise AssertionError("unreachable")

        injected_wrapper._fastdepends_call_ = real_model.call  # type: ignore[attr-defined]
        return wraps(func)(injected_wrapper)

    return func_wrapper


async def solve_async_gen(
    model: "CallModel", context: dict[str, Any], /, *args: Any, **kwargs: Any
) -> AsyncIterator[Any]:
    async with AsyncExitStack() as stack:
        values = await model.asolve(
            stack=stack,
            cache_dependencies={},
            nested=False,
            arguments=(args, kwargs),
            context=context,
        )
        async with aclosing(values):
            async for value in values:
                yield value


def solve_gen(
    model: "CallModel", context: dict[str, Any], /, *args: Any, **kwargs: Any
) -> Iterator[Any]:
    with ExitStack() as stack:
        values = model.solve(
            stack=stack,
            cache_dependencies={},
            nested=False,
            arguments=(args, kwargs),
            context=context,
        )
        with closing(values):
            yield from values
