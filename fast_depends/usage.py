from contextlib import AsyncExitStack, ExitStack
from functools import partial, wraps
from typing import Any, Callable, Optional, TypeVar

from pydantic import BaseModel, ValidationError, create_model

from fast_depends import model
from fast_depends.construct import get_dependant
from fast_depends.injector import (
    is_coroutine_callable,
    run_async,
    solve_dependencies_async,
    solve_dependencies_sync,
)
from fast_depends.provider import dependency_provider
from fast_depends.types import AnyCallable, P
from fast_depends.utils import args_to_kwargs

T = TypeVar("T")


def Depends(  # noqa: N802
    dependency: Optional[AnyCallable] = None, *, use_cache: bool = True
) -> Any:
    return model.Depends(dependency=dependency, use_cache=use_cache)


def inject(
    func: Callable[P, T],
    *,
    dependency_overrides_provider: Optional[Any] = dependency_provider,
) -> Callable[P, T]:
    dependant = get_dependant(call=func, path=func.__name__)
    error_model = create_model(func.__name__)

    if is_coroutine_callable(func) is True:
        f = async_typed_wrapper
    else:
        f = sync_typed_wrapper

    return wraps(func)(
        partial(
            f,
            dependant=dependant,
            error_model=error_model,
            dependency_overrides_provider=dependency_overrides_provider,
        )
    )


async def async_typed_wrapper(
    *args: P.args,
    dependant: model.Dependant,
    error_model: BaseModel,
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
            raise ValidationError(errors, error_model)

        v, errors = dependant.cast_response(
            await run_async(dependant=dependant, values=solved_result)
        )

        if errors:
            raise ValidationError(errors, error_model)

        return v


def sync_typed_wrapper(
    *args: P.args,
    dependant: model.Dependant,
    error_model: BaseModel,
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
            raise ValidationError(errors, error_model)

        v, errors = dependant.cast_response(dependant.call(**solved_result))

        if errors:
            raise ValidationError(errors, error_model)

        return v
