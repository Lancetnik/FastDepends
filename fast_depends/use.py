from contextlib import AsyncExitStack, ExitStack
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, Sequence, Union, overload

from typing_extensions import ParamSpec, Protocol, TypeVar

from fast_depends.core import CallModel, build_call_model
from fast_depends.dependencies import dependency_provider, model

P = ParamSpec("P")
T = TypeVar("T")


def Depends(
    dependency: Union[
        Callable[P, T],
        Callable[P, Awaitable[T]],
    ],
    *,
    use_cache: bool = True,
    cast: bool = True,
) -> model.Depends:
    return model.Depends(
        dependency=dependency,
        use_cache=use_cache,
        cast=cast,
    )


class _InjectWrapper(Protocol[P, T]):
    def __call__(
        self,
        func: Union[Callable[P, T], Callable[P, Awaitable[T]]],
        model: Optional[CallModel[P, T]] = None,
    ) -> Union[Callable[P, T], Callable[P, Awaitable[T]]]:
        ...


@overload
def inject(  # pragma: no covers
    func: None,
    *,
    dependency_overrides_provider: Optional[Any] = dependency_provider,
    extra_dependencies: Sequence[model.Depends] = (),
    wrap_model: Callable[[CallModel[P, T]], CallModel[P, T]] = lambda x: x,
) -> _InjectWrapper[P, T]:
    ...


@overload
def inject(  # pragma: no covers
    func: Callable[P, T],
    *,
    dependency_overrides_provider: Optional[Any] = dependency_provider,
    extra_dependencies: Sequence[model.Depends] = (),
    wrap_model: Callable[[CallModel[P, T]], CallModel[P, T]] = lambda x: x,
) -> Callable[P, T]:
    ...


def inject(
    func: Optional[Union[Callable[P, T], Callable[P, Awaitable[T]]]] = None,
    *,
    dependency_overrides_provider: Optional[Any] = dependency_provider,
    extra_dependencies: Sequence[model.Depends] = (),
    wrap_model: Callable[[CallModel[P, T]], CallModel[P, T]] = lambda x: x,
) -> Union[Union[Callable[P, T], Callable[P, Awaitable[T]]], _InjectWrapper[P, T],]:
    decorator = _wrap_inject(
        dependency_overrides_provider=dependency_overrides_provider,
        wrap_model=wrap_model,
        extra_dependencies=extra_dependencies,
    )

    if func is None:
        return decorator

    else:
        return decorator(func)


def _resolve_overrides_provider(
    dependency_overrides_provider: Optional[Any],
) -> Optional[dict[Callable[..., Any], Callable[..., Any]]]:
    if not dependency_overrides_provider:
        return None

    return getattr(dependency_overrides_provider, "dependency_overrides", None)


def _wrap_inject(
    dependency_overrides_provider: Optional[Any],
    wrap_model: Callable[
        [CallModel[P, T]],
        CallModel[P, T],
    ],
    extra_dependencies: Sequence[model.Depends],
) -> _InjectWrapper[P, T]:
    def func_wrapper(
        func: Union[Callable[P, T], Callable[P, Awaitable[T]]],
        model: Optional[CallModel[P, T]] = None,
    ) -> Union[Callable[P, T], Callable[P, Awaitable[T]]]:
        if model is None:
            real_model = wrap_model(
                build_call_model(
                    func,
                    extra_dependencies=extra_dependencies,
                )
            )
        else:
            real_model = model

        if real_model.is_async:

            @wraps(func)
            async def injected_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                async with AsyncExitStack() as stack:
                    r = await real_model.asolve(
                        *args,
                        stack=stack,
                        dependency_overrides=_resolve_overrides_provider(
                            dependency_overrides_provider
                        ),
                        cache_dependencies={},
                        **kwargs,
                    )
                    return r
                raise AssertionError("unreachable")

        else:

            @wraps(func)
            def injected_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                with ExitStack() as stack:
                    r = real_model.solve(
                        *args,
                        stack=stack,
                        dependency_overrides=_resolve_overrides_provider(
                            dependency_overrides_provider
                        ),
                        cache_dependencies={},
                        **kwargs,
                    )
                    return r
                raise AssertionError("unreachable")

        return injected_wrapper

    return func_wrapper
