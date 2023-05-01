import asyncio
import functools
import inspect
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    ContextManager,
    Dict,
    Iterable,
    TypeVar,
    cast,
)

import anyio

from fast_depends.types import AnyCallable, AnyDict, P

T = TypeVar("T")


def args_to_kwargs(
    arguments: Iterable[str], *args: P.args, **kwargs: P.kwargs
) -> AnyDict:
    if not args:
        return kwargs

    unused = filter(lambda x: x not in kwargs, arguments)

    return dict((*zip(unused, args), *kwargs.items()))


async def run_async(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    if asyncio.iscoroutinefunction(func):
        r = await func(*args, **kwargs)
        return cast(T, r)
    else:
        return await run_in_threadpool(func, *args, **kwargs)


async def run_in_threadpool(
    func: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    if kwargs:  # pragma: no cover
        func = functools.partial(func, **kwargs)
    return await anyio.to_thread.run_sync(func, *args)


def is_async_gen_callable(call: AnyCallable) -> bool:
    if inspect.isasyncgenfunction(call):
        return True
    dunder_call = getattr(call, "__call__", None)  # noqa: B004
    return inspect.isasyncgenfunction(dunder_call)


def is_gen_callable(call: AnyCallable) -> bool:
    if inspect.isgeneratorfunction(call):
        return True
    dunder_call = getattr(call, "__call__", None)  # noqa: B004
    return inspect.isgeneratorfunction(dunder_call)


def is_coroutine_callable(call: AnyCallable) -> bool:
    if inspect.isroutine(call):
        return inspect.iscoroutinefunction(call)
    if inspect.isclass(call):
        return False
    call_ = getattr(call, "__call__", None)  # noqa: B004
    return inspect.iscoroutinefunction(call_)


async def solve_generator_async(
    *, call: AnyCallable, stack: AsyncExitStack, sub_values: Dict[str, Any]
) -> Any:
    if is_gen_callable(call):
        cm = contextmanager_in_threadpool(contextmanager(call)(**sub_values))
    elif is_async_gen_callable(call):  # pragma: no branch
        cm = asynccontextmanager(call)(**sub_values)
    return await stack.enter_async_context(cm)


def solve_generator_sync(
    *, call: AnyCallable, stack: ExitStack, sub_values: Dict[str, Any]
) -> Any:
    cm = contextmanager(call)(**sub_values)
    return stack.enter_context(cm)


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
