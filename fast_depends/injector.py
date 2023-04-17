from contextlib import AsyncExitStack, ExitStack
from copy import deepcopy
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    cast,
)

from pydantic.error_wrappers import ErrorWrapper
from pydantic.errors import MissingError
from pydantic.fields import ModelField

from fast_depends.construct import get_dependant
from fast_depends.model import Dependant
from fast_depends.types import AnyCallable, AnyDict
from fast_depends.utils import (
    run_async,
    is_coroutine_callable,
    is_gen_callable,
    is_async_gen_callable,
    solve_generator_async,
    solve_generator_sync,
)


T = TypeVar("T")


async def solve_dependencies_async(
    *,
    dependant: Dependant,
    stack: AsyncExitStack,
    body: Optional[AnyDict] = None,
    dependency_overrides_provider: Optional[Any] = None,
    dependency_cache: Optional[Dict[Tuple[AnyCallable, Tuple[str]], Any]] = None,
) -> Tuple[
    Dict[str, Any],
    List[ErrorWrapper],
    Dict[Tuple[AnyCallable, Tuple[str]], Any],
]:
    errors: List[ErrorWrapper] = []

    dependency_cache = dependency_cache or {}

    sub_dependant: Dependant
    for sub_dependant in dependant.dependencies:
        sub_dependant.call = cast(AnyCallable, sub_dependant.call)
        sub_dependant.cache_key = cast(
            Tuple[AnyCallable, Tuple[str]], sub_dependant.cache_key
        )
        call = sub_dependant.call
        use_sub_dependant = sub_dependant
        if (
            dependency_overrides_provider
            and dependency_overrides_provider.dependency_overrides
        ):
            call = getattr(
                dependency_overrides_provider, "dependency_overrides", {}
            ).get(sub_dependant.call)
            if call is not None:  # pragma: no branch
                use_sub_dependant = get_dependant(
                    path=sub_dependant.path,
                    call=call,
                    name=sub_dependant.name,
                )

        solved_result = await solve_dependencies_async(
            dependant=use_sub_dependant,
            body=body,
            dependency_overrides_provider=dependency_overrides_provider,
            dependency_cache=dependency_cache,
            stack=stack,
        )
        (
            sub_values,
            sub_errors,
            sub_dependency_cache,
        ) = solved_result

        dependency_cache.update(sub_dependency_cache)

        if sub_errors:
            errors.extend(sub_errors)
            continue

        if (
            use_sub_dependant.use_cache
            and use_sub_dependant.cache_key in dependency_cache
        ):
            solved = dependency_cache[use_sub_dependant.cache_key]
        elif is_gen_callable(call) or is_async_gen_callable(call):
            solved, sub_errors = use_sub_dependant.cast_response(
                await solve_generator_async(
                    call=call, stack=stack, sub_values=sub_values
                )
            )
        else:
            solved, sub_errors = use_sub_dependant.cast_response(
                await run_async(use_sub_dependant.call, **sub_values)
            )

        if sub_errors:
            errors.append(sub_errors)
            continue

        if use_sub_dependant.name is not None:  # pragma: no branch
            body[use_sub_dependant.name] = solved

        if use_sub_dependant.cache_key not in dependency_cache:
            dependency_cache[use_sub_dependant.cache_key] = solved

    params, main_errors = params_to_args(dependant.params, body or {})
    errors.extend(main_errors)
    return params, errors, dependency_cache


def solve_dependencies_sync(
    *,
    dependant: Dependant,
    stack: ExitStack,
    body: Optional[AnyDict] = None,
    dependency_overrides_provider: Optional[Any] = None,
    dependency_cache: Optional[Dict[Tuple[AnyCallable, Tuple[str]], Any]] = None,
) -> Tuple[
    Dict[str, Any],
    List[ErrorWrapper],
    Dict[Tuple[AnyCallable, Tuple[str]], Any],
]:
    assert not is_coroutine_callable(dependant.call) and not is_async_gen_callable(
        dependant.call
    ), f"You can't call async `{dependant.call.__name__}` at sync code"

    errors: List[ErrorWrapper] = []

    dependency_cache = dependency_cache or {}

    sub_dependant: Dependant
    for sub_dependant in dependant.dependencies:
        sub_dependant.call = cast(AnyCallable, sub_dependant.call)
        sub_dependant.cache_key = cast(
            Tuple[AnyCallable, Tuple[str]], sub_dependant.cache_key
        )
        call = sub_dependant.call
        use_sub_dependant = sub_dependant
        if (
            dependency_overrides_provider
            and dependency_overrides_provider.dependency_overrides
        ):
            call = getattr(
                dependency_overrides_provider, "dependency_overrides", {}
            ).get(sub_dependant.call)
            if call is not None:  # pragma: no branch
                use_sub_dependant = get_dependant(
                    path=sub_dependant.path,
                    call=call,
                    name=sub_dependant.name,
                )

        solved_result = solve_dependencies_sync(
            dependant=use_sub_dependant,
            body=body,
            stack=stack,
            dependency_overrides_provider=dependency_overrides_provider,
            dependency_cache=dependency_cache,
        )
        (
            sub_values,
            sub_errors,
            sub_dependency_cache,
        ) = solved_result

        dependency_cache.update(sub_dependency_cache)

        if sub_errors:
            errors.extend(sub_errors)
            continue

        if (
            use_sub_dependant.use_cache
            and use_sub_dependant.cache_key in dependency_cache
        ):
            solved = dependency_cache[sub_dependant.cache_key]
        elif is_gen_callable(call):
            solved, sub_errors = use_sub_dependant.cast_response(
                solve_generator_sync(call=call, stack=stack, sub_values=sub_values)
            )
        else:
            solved, sub_errors = use_sub_dependant.cast_response(call(**sub_values))

        if sub_errors:
            errors.append(sub_errors)
            continue

        if use_sub_dependant.name is not None:  # pragma: no branch
            body[sub_dependant.name] = solved

        if use_sub_dependant.cache_key not in dependency_cache:
            dependency_cache[use_sub_dependant.cache_key] = solved

    params, main_errors = params_to_args(dependant.params, body or {})
    errors.extend(main_errors)
    return params, errors, dependency_cache


def params_to_args(
    required_params: Sequence[ModelField],
    received_params: Mapping[str, Any],
) -> Tuple[AnyDict, List[ErrorWrapper]]:
    values: AnyDict = {}
    errors: List[ErrorWrapper] = []
    for field in required_params:
        value = received_params.get(field.alias)
        if value is None:
            if field.required:
                errors.append(ErrorWrapper(MissingError(), loc=(field.alias,)))
            else:
                values[field.name] = deepcopy(field.default)
            continue

        v_, errors_ = field.validate(value, values, loc=(field.alias,))
        if isinstance(errors_, ErrorWrapper):
            errors.append(errors_)
        elif isinstance(errors_, list):  # pragma: no cover
            errors.extend(errors_)
        else:
            values[field.name] = v_
    return values, errors
