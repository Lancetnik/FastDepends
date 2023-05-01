from contextlib import AsyncExitStack, ExitStack
from functools import partial, wraps
from typing import Any, Callable, Optional, TypeVar

from pydantic import ValidationError

from fast_depends import model
from fast_depends.construct import get_dependant
from fast_depends.injector import solve_dependencies_async, solve_dependencies_sync
from fast_depends.provider import dependency_provider
from fast_depends.types import AnyCallable, P
from fast_depends.utils import args_to_kwargs, is_coroutine_callable, run_async

T = TypeVar("T")


def Depends(dependency: AnyCallable, *, use_cache: bool = True) -> Any:  # noqa: N802
    return model.Depends(dependency=dependency, use_cache=use_cache)


def wrap_dependant(dependant: model.Dependant) -> model.Dependant:
    return dependant


def inject(
    func: Callable[P, T],
    *,
    dependency_overrides_provider: Optional[Any] = dependency_provider,
    wrap_dependant: Callable[[model.Dependant], model.Dependant] = wrap_dependant,
) -> Callable[P, T]:
    dependant = get_dependant(call=func, path=func.__name__)

    dependant = wrap_dependant(dependant)

    if is_coroutine_callable(func) is True:
        f = async_typed_wrapper
    else:
        f = sync_typed_wrapper

    return wraps(func)(
        partial(
            f,
            dependant=dependant,
            dependency_overrides_provider=dependency_overrides_provider,
        )
    )


async def async_typed_wrapper(
    *args: P.args,
    dependant: model.Dependant,
    dependency_overrides_provider: Optional[Any],
    **kwargs: P.kwargs,
) -> Any:
    kwargs = args_to_kwargs((x.name for x in dependant.params), *args, **kwargs)

    async with AsyncExitStack() as stack:
        solved_result, errors, _ = await solve_dependencies_async(
            body=kwargs,
            dependant=dependant,
            stack=stack,
            dependency_overrides_provider=dependency_overrides_provider,
        )

        if errors:
            raise ValidationError(errors, dependant.error_model)

        v, casted_errors = dependant.cast_response(
            await run_async(dependant.call, **solved_result)
        )

        if casted_errors:
            raise ValidationError(errors, dependant.error_model)

        return v


def sync_typed_wrapper(
    *args: P.args,
    dependant: model.Dependant,
    dependency_overrides_provider: Optional[Any],
    **kwargs: P.kwargs,
) -> Any:
    kwargs = args_to_kwargs((x.name for x in dependant.params), *args, **kwargs)

    with ExitStack() as stack:
        solved_result, errors, _ = solve_dependencies_sync(
            body=kwargs,
            dependant=dependant,
            stack=stack,
            dependency_overrides_provider=dependency_overrides_provider,
        )

        if errors:
            raise ValidationError(errors, dependant.error_model)

        v, casted_errors = dependant.cast_response(dependant.call(**solved_result))

        if casted_errors:
            raise ValidationError(errors, dependant.error_model)

        return v
