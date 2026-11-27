import functools
import inspect
import sys
from collections.abc import (
    AsyncGenerator,
    AsyncIterable,
    Awaitable,
    Callable,
    Generator,
    Iterator,
)
from contextlib import (
    AbstractContextManager,
    aclosing,
    asynccontextmanager,
    closing,
)
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ForwardRef,
    TypeVar,
    cast,
    get_args,
    get_origin,
    overload,
)

if sys.version_info >= (3, 12):
    from typing import TypeAliasType
else:
    from typing_extensions import TypeAliasType

import anyio
from typing_extensions import ParamSpec

from fast_depends._compat import evaluate_forwardref

if TYPE_CHECKING:
    from types import FrameType

P = ParamSpec("P")
T = TypeVar("T")


@overload
async def run_async(
    func: Callable[P, Awaitable[T]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T: ...


@overload
async def run_async(
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T: ...


async def run_async(
    func: Callable[P, T] | Callable[P, Awaitable[T]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    if is_coroutine_callable(func):
        return await cast(Callable[P, Awaitable[T]], func)(*args, **kwargs)
    else:
        return await run_in_threadpool(cast(Callable[P, T], func), *args, **kwargs)


async def run_in_threadpool(
    func: Callable[P, T],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    if kwargs:
        func = functools.partial(func, **kwargs)
    return await anyio.to_thread.run_sync(func, *args)


def _prepare_async_call(
    call: Callable[..., Any],
) -> Callable[..., Awaitable[Any]]:
    if is_coroutine_callable(call):
        return cast(Callable[..., Awaitable[Any]], call)
    return functools.partial(run_in_threadpool, call)


def get_typed_signature(call: Callable[..., Any]) -> tuple[inspect.Signature, Any]:
    signature = inspect.signature(call)

    locals = collect_outer_stack_locals()

    # We unwrap call to get the original unwrapped function
    call = inspect.unwrap(call)

    type_params = getattr(call, "__type_params__", ()) or None

    globalns = getattr(call, "__globals__", {})
    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=get_typed_annotation(
                param.annotation,
                globalns,
                locals,
                type_params=type_params,
            ),
        )
        for param in signature.parameters.values()
    ]

    return inspect.Signature(typed_params), get_typed_annotation(
        signature.return_annotation,
        globalns,
        locals,
        type_params=type_params,
    )


def collect_outer_stack_locals() -> dict[str, Any]:
    frame = inspect.currentframe()

    frames: list[FrameType] = []
    while frame is not None:
        if "fast_depends" not in frame.f_code.co_filename:
            frames.append(frame)
        frame = frame.f_back

    locals = {}
    for f in frames[::-1]:
        locals.update(f.f_locals)

    return locals


def get_typed_annotation(
    annotation: Any,
    globalns: dict[str, Any],
    locals: dict[str, Any],
    type_params: tuple[Any, ...] | None = None,
) -> Any:
    if isinstance(annotation, TypeAliasType):
        annotation = annotation.__value__

    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)

    if isinstance(annotation, ForwardRef):
        annotation = evaluate_forwardref(
            annotation, globalns, locals, type_params=type_params
        )

    if get_origin(annotation) is Annotated and (args := get_args(annotation)):
        solved_args = [
            get_typed_annotation(x, globalns, locals, type_params=type_params)
            for x in args
        ]

        annotation.__origin__, annotation.__metadata__ = (
            solved_args[0],
            tuple(solved_args[1:]),
        )

    return annotation


@asynccontextmanager
async def contextmanager_in_threadpool(
    cm: AbstractContextManager[T],
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

    if inspect.iscoroutinefunction(call):
        return True

    dunder_call = getattr(call, "__call__", None)  # noqa: B004
    return inspect.iscoroutinefunction(dunder_call)


async def async_map(
    func: Callable[..., T], async_iterable: AsyncGenerator[Any, Any]
) -> AsyncIterable[T]:
    async with aclosing(async_iterable):
        async for i in async_iterable:
            yield func(i)


def sync_map(func: Callable[..., T], values: Generator[Any, Any, Any]) -> Iterator[T]:
    with closing(values):
        yield from map(func, values)
