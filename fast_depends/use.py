from contextlib import AsyncExitStack, ExitStack
from functools import partial, wraps
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Iterator,
    Optional,
    Sequence,
    Union,
    overload,
)

from typing_extensions import ParamSpec, Protocol, TypeVar

from fast_depends.core import CallModel, build_call_model
from fast_depends.dependencies import dependency_provider, model

P = ParamSpec("P")
T = TypeVar("T")


def Depends(
    dependency: Callable[P, T],
    *,
    use_cache: bool = True,
    cast: bool = True,
) -> Any:
    return model.Depends(
        dependency=dependency,
        use_cache=use_cache,
        cast=cast,
    )


class _InjectWrapper(Protocol[P, T]):
    def __call__(
        self,
        func: Callable[P, T],
        model: Optional[CallModel[P, T]] = None,
    ) -> Callable[P, T]:
        ...


@overload
def inject(  # pragma: no cover
    func: None,
    *,
    dependency_overrides_provider: Optional[Any] = dependency_provider,
    extra_dependencies: Sequence[model.Depends] = (),
    wrap_model: Callable[[CallModel[P, T]], CallModel[P, T]] = lambda x: x,
    cast: bool = True,
) -> _InjectWrapper[P, T]:
    ...


@overload
def inject(  # pragma: no cover
    func: Callable[P, T],
    *,
    dependency_overrides_provider: Optional[Any] = dependency_provider,
    extra_dependencies: Sequence[model.Depends] = (),
    wrap_model: Callable[[CallModel[P, T]], CallModel[P, T]] = lambda x: x,
    cast: bool = True,
) -> Callable[P, T]:
    ...


def inject(
    func: Optional[Callable[P, T]] = None,
    *,
    dependency_overrides_provider: Optional[Any] = dependency_provider,
    extra_dependencies: Sequence[model.Depends] = (),
    wrap_model: Callable[[CallModel[P, T]], CallModel[P, T]] = lambda x: x,
    cast: bool = True,
) -> Union[Callable[P, T], _InjectWrapper[P, T],]:
    decorator = _wrap_inject(
        dependency_overrides_provider=dependency_overrides_provider,
        wrap_model=wrap_model,
        extra_dependencies=extra_dependencies,
        cast=cast,
    )

    if func is None:
        return decorator

    else:
        return decorator(func)


def _wrap_inject(
    dependency_overrides_provider: Optional[Any],
    wrap_model: Callable[
        [CallModel[P, T]],
        CallModel[P, T],
    ],
    extra_dependencies: Sequence[model.Depends],
    cast: bool,
) -> _InjectWrapper[P, T]:
    if (
        dependency_overrides_provider
        and getattr(dependency_overrides_provider, "dependency_overrides", None)
        is not None
    ):
        overrides = dependency_overrides_provider.dependency_overrides
    else:
        overrides = None

    def func_wrapper(
        func: Callable[P, T],
        model: Optional[CallModel[P, T]] = None,
    ) -> Callable[P, T]:
        if model is None:
            real_model = wrap_model(
                build_call_model(
                    func,
                    extra_dependencies=extra_dependencies,
                    cast=cast,
                )
            )
        else:
            real_model = model

        if real_model.is_async:
            injected_wrapper: Callable[P, T]

            if real_model.is_generator:
                injected_wrapper = partial(solve_async_gen, real_model, overrides)  # type: ignore[assignment]

            else:

                @wraps(func)
                async def injected_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                    async with AsyncExitStack() as stack:
                        r = await real_model.asolve(
                            *args,
                            stack=stack,
                            dependency_overrides=overrides,
                            cache_dependencies={},
                            nested=False,
                            **kwargs,
                        )
                        return r

                    raise AssertionError("unreachable")

        else:
            if real_model.is_generator:
                injected_wrapper = partial(solve_gen, real_model, overrides)  # type: ignore[assignment]

            else:

                @wraps(func)
                def injected_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                    with ExitStack() as stack:
                        r = real_model.solve(
                            *args,
                            stack=stack,
                            dependency_overrides=overrides,
                            cache_dependencies={},
                            nested=False,
                            **kwargs,
                        )
                        return r
                    raise AssertionError("unreachable")

        return injected_wrapper

    return func_wrapper


class solve_async_gen:
    iter: Optional[AsyncIterator[Any]]

    def __init__(
        self,
        model: "CallModel[..., Any]",
        overrides: Optional[Any],
        *args: Any,
        **kwargs: Any,
    ):
        self.call = model
        self.args = args
        self.kwargs = kwargs
        self.overrides = overrides

    def __aiter__(self) -> "solve_async_gen":
        self.iter = None
        self.stack = AsyncExitStack()
        return self

    async def __anext__(self) -> Any:
        if self.iter is None:
            stack = self.stack = AsyncExitStack()
            await self.stack.__aenter__()
            self.iter: AsyncIterator[Any] = (
                await self.call.asolve(
                    *self.args,
                    stack=stack,
                    dependency_overrides=self.overrides,
                    cache_dependencies={},
                    nested=False,
                    **self.kwargs,
                )
            ).__aiter__()

        try:
            r = await self.iter.__anext__()
        except StopAsyncIteration as e:
            await self.stack.__aexit__(None, None, None)
            raise e
        else:
            return r


class solve_gen:
    iter: Optional[Iterator[Any]]

    def __init__(
        self,
        model: "CallModel[..., Any]",
        overrides: Optional[Any],
        *args: Any,
        **kwargs: Any,
    ):
        self.call = model
        self.args = args
        self.kwargs = kwargs
        self.overrides = overrides

    def __iter__(self) -> "solve_gen":
        self.iter = None
        self.stack = ExitStack()
        return self

    def __next__(self) -> Any:
        if self.iter is None:
            stack = self.stack = ExitStack()
            self.stack.__enter__()
            self.iter: AsyncIterator[Any] = iter(
                self.call.solve(
                    *self.args,
                    stack=stack,
                    dependency_overrides=self.overrides,
                    cache_dependencies={},
                    nested=False,
                    **self.kwargs,
                )
            )

        try:
            r = next(self.iter)
        except StopIteration as e:
            self.stack.__exit__(None, None, None)
            raise e
        else:
            return r
