from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import AsyncExitStack, ExitStack
from functools import partial, wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import Literal, ParamSpec

from fast_depends.core import CallModel, build_call_model
from fast_depends.dependencies import Dependant, Provider
from fast_depends.library.serializer import SerializerProto

SerializerCls: Optional["SerializerProto"] = None

if SerializerCls is None:
    try:
        from fast_depends.pydantic import PydanticSerializer
        SerializerCls = PydanticSerializer()
    except ImportError:
        pass

if SerializerCls is None:
    try:
        from fast_depends.msgspec import MsgSpecSerializer
        SerializerCls = MsgSpecSerializer
    except ImportError:
        pass


P = ParamSpec("P")
T = TypeVar("T")

if TYPE_CHECKING:
    from fast_depends.library.serializer import SerializerProto

    class InjectWrapper(Protocol):
        def __call__(
            self,
            func: Callable[..., T],
            model: Optional[CallModel] = None,
        ) -> Callable[..., T]:
            ...


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


@overload
def inject(
    func: Callable[..., T],
    *,
    cast: bool = True,
    cast_result: bool = True,
    extra_dependencies: Sequence[Dependant] = (),
    dependency_provider: Optional["Provider"] = None,
    wrap_model: Callable[["CallModel"], "CallModel"] = lambda x: x,
    serializer_cls: Optional["SerializerProto"] = SerializerCls,
    **call_extra: Any,
) -> Callable[..., T]:
    ...

@overload
def inject(
    func: Literal[None] = None,
    *,
    cast: bool = True,
    cast_result: bool = True,
    extra_dependencies: Sequence[Dependant] = (),
    dependency_provider: Optional["Provider"] = None,
    wrap_model: Callable[["CallModel"], "CallModel"] = lambda x: x,
    serializer_cls: Optional["SerializerProto"] = SerializerCls,
    **call_extra: Any,
) -> "InjectWrapper":
    ...

def inject(
    func: Optional[Callable[..., T]] = None,
    *,
    cast: bool = True,
    cast_result: bool = True,
    extra_dependencies: Sequence[Dependant] = (),
    dependency_provider: Optional["Provider"] = None,
    wrap_model: Callable[["CallModel"], "CallModel"] = lambda x: x,
    serializer_cls: Optional["SerializerProto"] = SerializerCls,
    **call_extra: Any,
) -> Union[
    Callable[..., T],
    Callable[
        [Callable[..., T]],
        Callable[..., T]
    ],
]:
    if dependency_provider is None:
        dependency_provider = Provider()

    if not cast:
        serializer_cls = None

    decorator = _wrap_inject(
        dependency_provider=dependency_provider,
        wrap_model=wrap_model,
        extra_dependencies=extra_dependencies,
        serializer_cls=serializer_cls,
        cast_result=cast_result,
        **call_extra,
    )

    if func is None:
        return decorator

    else:
        return decorator(func)


def _wrap_inject(
    *,
    dependency_provider: "Provider",
    wrap_model: Callable[["CallModel"], "CallModel"],
    extra_dependencies: Sequence[Dependant],
    serializer_cls: Optional["SerializerProto"],
    cast_result: bool,
    **call_extra: Any,
) -> Callable[
    [Callable[P, T]],
    Callable[..., T]
]:
    def func_wrapper(
        func: Callable[P, T],
        model: Optional["CallModel"] = None,
    ) -> Callable[..., T]:
        if model is None:
            real_model = wrap_model(
                build_call_model(
                    call=func,
                    extra_dependencies=extra_dependencies,
                    dependency_provider=dependency_provider,
                    serializer_cls=serializer_cls,
                    serialize_result=cast_result,
                )
            )
        else:
            real_model = model

        if real_model.is_async:
            injected_wrapper: Callable[..., T]

            if real_model.is_generator:
                injected_wrapper = partial(  # type: ignore[assignment]
                    solve_async_gen,
                    real_model,
                )

            else:

                async def injected_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:  # type: ignore[misc]
                    async with AsyncExitStack() as stack:
                        return await real_model.asolve(  # type: ignore[no-any-return]
                            *args,
                            stack=stack,
                            cache_dependencies={},
                            nested=False,
                            **(call_extra | kwargs),
                        )

                    raise AssertionError("unreachable")

        else:
            if real_model.is_generator:
                injected_wrapper = partial(  # type: ignore[assignment]
                    solve_gen,
                    real_model,
                )

            else:

                def injected_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                    with ExitStack() as stack:
                        return real_model.solve(  # type: ignore[no-any-return]
                            *args,
                            stack=stack,
                            cache_dependencies={},
                            nested=False,
                                **(call_extra | kwargs),
                        )

                    raise AssertionError("unreachable")

        return wraps(func)(injected_wrapper)

    return func_wrapper


class solve_async_gen:
    _iter: Optional[AsyncIterator[Any]] = None

    def __init__(
        self,
        model: "CallModel",
        *args: Any,
        **kwargs: Any,
    ):
        self.call = model
        self.args = args
        self.kwargs = kwargs

    def __aiter__(self) -> "solve_async_gen":
        self._iter = None
        self.stack = AsyncExitStack()
        return self

    async def __anext__(self) -> Any:
        if self._iter is None:
            stack = self.stack = AsyncExitStack()
            await self.stack.__aenter__()
            self._iter = cast(
                AsyncIterator[Any],
                (
                    await self.call.asolve(
                        *self.args,
                        stack=stack,
                        cache_dependencies={},
                        nested=False,
                        **self.kwargs,
                    )
                ).__aiter__(),
            )

        try:
            r = await self._iter.__anext__()
        except StopAsyncIteration:
            await self.stack.__aexit__(None, None, None)
            raise
        else:
            return r


class solve_gen:
    _iter: Optional[Iterator[Any]] = None

    def __init__(
        self,
        model: "CallModel",
        *args: Any,
        **kwargs: Any,
    ):
        self.call = model
        self.args = args
        self.kwargs = kwargs

    def __iter__(self) -> "solve_gen":
        self._iter = None
        self.stack = ExitStack()
        return self

    def __next__(self) -> Any:
        if self._iter is None:
            stack = self.stack = ExitStack()
            self.stack.__enter__()
            self._iter = cast(
                Iterator[Any],
                iter(
                    self.call.solve(
                        *self.args,
                        stack=stack,
                        cache_dependencies={},
                        nested=False,
                        **self.kwargs,
                    )
                ),
            )

        try:
            r = next(self._iter)
        except StopIteration:
            self.stack.__exit__(None, None, None)
            raise
        else:
            return r
