import asyncio
import functools
import inspect
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    ContextManager,
    Dict,
    ForwardRef,
    List,
    Tuple,
    Union,
    cast,
)

import anyio
from typing_extensions import ParamSpec, TypeVar

from fast_depends._compat import evaluate_forwardref

P = ParamSpec("P")
T = TypeVar("T")


async def run_async(
    func: Union[
        Callable[P, T],
        Callable[P, Awaitable[T]],
    ],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    if is_coroutine_callable(func):
        return await cast(Callable[P, Awaitable[T]], func)(*args, **kwargs)
    else:
        return await run_in_threadpool(cast(Callable[P, T], func), *args, **kwargs)


async def run_in_threadpool(
    func: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    if kwargs:  # pragma: no cover
        func = functools.partial(func, **kwargs)
    return await anyio.to_thread.run_sync(func, *args)


async def solve_generator_async(
    *sub_args: Any, call: Callable[..., Any], stack: AsyncExitStack, **sub_values: Any
) -> Any:
    if is_gen_callable(call):
        cm = contextmanager_in_threadpool(contextmanager(call)(**sub_values))
    elif is_async_gen_callable(call):  # pragma: no branch
        cm = asynccontextmanager(call)(*sub_args, **sub_values)
    return await stack.enter_async_context(cm)


def solve_generator_sync(
    *sub_args: Any, call: Callable[..., Any], stack: ExitStack, **sub_values: Any
) -> Any:
    cm = contextmanager(call)(*sub_args, **sub_values)
    return stack.enter_context(cm)


def get_typed_signature(
    call: Callable[..., Any]
) -> Tuple[List[inspect.Parameter], Any]:
    signature = inspect.signature(call)
    globalns = getattr(call, "__globals__", {})

    return [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=get_typed_annotation(param.annotation, globalns),
        )
        for param in signature.parameters.values()
    ], signature.return_annotation


def get_typed_annotation(annotation: Any, globalns: Dict[str, Any]) -> Any:
    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)
        annotation = evaluate_forwardref(annotation, globalns, globalns)
    return annotation


@asynccontextmanager
async def contextmanager_in_threadpool(
    cm: ContextManager[T],
) -> AsyncGenerator[T, None]:
    exit_limiter = anyio.CapacityLimiter(1)
    try:
        yield await run_in_threadpool(cm.__enter__)
    except Exception as e:
        ok = bool(
            await anyio.to_thread.run_sync(
                cm.__exit__, type(e), e, None, limiter=exit_limiter
            )
        )
        if not ok:  # pragma: no branch
            raise e
    else:
        await anyio.to_thread.run_sync(
            cm.__exit__, None, None, None, limiter=exit_limiter
        )


def is_gen_callable(call: Callable[..., Any]) -> bool:
    if inspect.isgeneratorfunction(call):
        return True
    dunder_call = getattr(call, "__call__", None)  # noqa: B004
    return inspect.isgeneratorfunction(dunder_call)


def is_async_gen_callable(call: Callable[..., Any]) -> bool:
    if inspect.isasyncgenfunction(call):
        return True
    dunder_call = getattr(call, "__call__", None)  # noqa: B004
    return inspect.isasyncgenfunction(dunder_call)


def is_coroutine_callable(call: Callable[..., Any]) -> bool:
    if inspect.isclass(call):
        return False

    if asyncio.iscoroutinefunction(call):
        return True

    call_ = getattr(call, "__call__", None)  # noqa: B004
    return asyncio.iscoroutinefunction(call_)
