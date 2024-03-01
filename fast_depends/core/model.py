from contextlib import AsyncExitStack, ExitStack
from inspect import Parameter, unwrap
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import anyio
from typing_extensions import ParamSpec, TypeVar

from fast_depends._compat import ExceptionGroup
from fast_depends.library.caster import Caster, OptionItem
from fast_depends.library.model import CustomField
from fast_depends.utils import (
    async_map,
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
    run_async,
    solve_generator_async,
    solve_generator_sync,
)

P = ParamSpec("P")
T = TypeVar("T")


class CallModel(Generic[P, T]):
    alias_arguments: Tuple[str, ...]

    __slots__ = (
        "call",
        "is_async",
        "is_generator",
        "params",
        "alias_arguments",
        "args_name",
        "positional_args",
        "kwargs_name",
        "keyword_args",
        "dependencies",
        "extra_dependencies",
        "custom_fields",
        "use_cache",
        "caster",
    )

    @property
    def call_name(self) -> str:
        call = unwrap(self.call)
        return getattr(call, "__name__", type(call).__name__)

    @property
    def flat_params(self) -> List[OptionItem]:
        params = list(self.params)
        for d in (*self.dependencies.values(), *self.extra_dependencies):
            for p in d.flat_params:
                if p.field_name not in (i.field_name for i in params):
                    params.append(p)
        return params

    def __init__(
        self,
        /,
        call: Union[
            Callable[P, T],
            Callable[P, Awaitable[T]],
        ],
        caster: Optional[Caster],
        params: Tuple[OptionItem, ...],
        use_cache: bool = True,
        is_async: bool = False,
        is_generator: bool = False,
        args_name: Optional[str] = None,
        kwargs_name: Optional[str] = None,
        dependencies: Optional[Dict[str, "CallModel[..., Any]"]] = None,
        extra_dependencies: Optional[Iterable["CallModel[..., Any]"]] = None,
        keyword_args: Optional[List[str]] = None,
        positional_args: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, CustomField]] = None,
    ):
        self.call = call
        self.caster = caster

        if caster is not None:
            self.alias_arguments = caster.get_aliases()
        else:
            self.alias_arguments = ()

        self.args_name = args_name
        self.keyword_args = tuple(keyword_args or ())
        self.kwargs_name = kwargs_name
        self.positional_args = tuple(positional_args or ())

        self.use_cache = use_cache
        self.is_async = (
            is_async or is_coroutine_callable(call) or is_async_gen_callable(call)
        )
        self.is_generator = (
            is_generator or is_gen_callable(call) or is_async_gen_callable(call)
        )

        self.dependencies = dependencies or {}
        self.extra_dependencies = tuple(extra_dependencies or ())
        self.custom_fields = custom_fields or {}

        self.params = params

    def _solve(
        self,
        /,
        *args: Tuple[Any, ...],
        cache_dependencies: Dict[
            Union[
                Callable[P, T],
                Callable[P, Awaitable[T]],
            ],
            T,
        ],
        dependency_overrides: Optional[
            Dict[
                Union[
                    Callable[P, T],
                    Callable[P, Awaitable[T]],
                ],
                Union[
                    Callable[P, T],
                    Callable[P, Awaitable[T]],
                ],
            ]
        ] = None,
        **kwargs: Dict[str, Any],
    ) -> Generator[
        Tuple[
            Sequence[Any],
            Dict[str, Any],
            Callable[..., Any],
        ],
        Any,
        T,
    ]:
        if dependency_overrides:
            call = dependency_overrides.get(self.call, self.call)
            assert self.is_async or not is_coroutine_callable(
                call
            ), f"You cannot use async dependency `{self.call_name}` at sync main"

        else:
            call = self.call

        if self.use_cache and call in cache_dependencies:
            return cache_dependencies[call]

        kw: Dict[str, Any] = {}
        for arg in self.keyword_args:
            if (v := kwargs.pop(arg, Parameter.empty)) is not Parameter.empty:
                kw[arg] = v

        if self.kwargs_name in self.alias_arguments:
            kw[self.kwargs_name] = kwargs
        else:
            kw.update(kwargs)

        for arg in filter(
            lambda x: x not in kw,
            self.positional_args,
        ):
            if args:
                kw[arg], args = args[0], args[1:]
            else:
                break

        if self.args_name in self.alias_arguments:
            kw[self.args_name] = args
            keyword_args = self.keyword_args

        else:
            keyword_args = set(self.keyword_args + self.positional_args)
            for arg in filter(
                lambda x: x not in kw,
                keyword_args - set(self.dependencies.keys())
            ):
                if args:
                    kw[arg], args = args[0], args[1:]
                else:
                    break

        solved_kw: Dict[str, Any]
        solved_kw = yield args, kw, call

        args_: Sequence[Any]
        if self.caster is not None:
            casted_options = self.caster(solved_kw)
            solved_kw.update(casted_options)
            args = ()

        if self.args_name:
            args_ = (
                *map(solved_kw.pop, self.positional_args),
                *solved_kw.get(self.args_name, args),
            )
        else:
            args_ = args

        kwargs_ = {
            arg: solved_kw.pop(arg)
            for arg in keyword_args
            if arg in solved_kw
        }
        if self.kwargs_name:
            kwargs_.update(solved_kw.get(self.kwargs_name, solved_kw))

        response: T = yield args_, kwargs_, call

        if self.caster is not None and not self.is_generator:
            response = self._cast_response(response)

        if self.use_cache:  # pragma: no branch
            cache_dependencies[call] = response

        return response

    def _cast_response(self, /, value: Any) -> Any:
        if self.caster is not None:
            return self.caster.response(value)
        return value

    def solve(
        self,
        /,
        *args: Tuple[Any, ...],
        stack: ExitStack,
        cache_dependencies: Dict[
            Union[
                Callable[P, T],
                Callable[P, Awaitable[T]],
            ],
            T,
        ],
        dependency_overrides: Optional[
            Dict[
                Union[
                    Callable[P, T],
                    Callable[P, Awaitable[T]],
                ],
                Union[
                    Callable[P, T],
                    Callable[P, Awaitable[T]],
                ],
            ]
        ] = None,
        nested: bool = False,
        **kwargs: Dict[str, Any],
    ) -> T:
        cast_gen = self._solve(
            *args,
            cache_dependencies=cache_dependencies,
            dependency_overrides=dependency_overrides,
            **kwargs,
        )
        try:
            args, kwargs, _ = next(cast_gen)
        except StopIteration as e:
            cached_value: T = e.value
            return cached_value

        for dep in self.extra_dependencies:
            dep.solve(
                *args,
                stack=stack,
                cache_dependencies=cache_dependencies,
                dependency_overrides=dependency_overrides,
                nested=True,
                **kwargs,
            )

        for dep_arg, dep in self.dependencies.items():
            if dep_arg not in kwargs:
                kwargs[dep_arg] = dep.solve(
                    *args,
                    stack=stack,
                    cache_dependencies=cache_dependencies,
                    dependency_overrides=dependency_overrides,
                    nested=True,
                    **kwargs,
                )

        for custom in self.custom_fields.values():
            if custom.field:
                custom.use_field(kwargs)
            else:
                kwargs = custom.use(**kwargs)

        final_args, final_kwargs, call = cast_gen.send(kwargs)

        if self.is_generator and nested:
            response = solve_generator_sync(
                *final_args,
                call=call,
                stack=stack,
                **final_kwargs,
            )

        else:
            response = call(*final_args, **final_kwargs)

        try:
            cast_gen.send(response)
        except StopIteration as e:
            value: T = e.value

            if self.caster is None or nested or not self.is_generator:
                return value

            else:
                return map(self._cast_response, value)  # type: ignore[no-any-return, call-overload]

        raise AssertionError("unreachable")

    async def asolve(
        self,
        /,
        *args: Tuple[Any, ...],
        stack: AsyncExitStack,
        cache_dependencies: Dict[
            Union[
                Callable[P, T],
                Callable[P, Awaitable[T]],
            ],
            T,
        ],
        dependency_overrides: Optional[
            Dict[
                Union[
                    Callable[P, T],
                    Callable[P, Awaitable[T]],
                ],
                Union[
                    Callable[P, T],
                    Callable[P, Awaitable[T]],
                ],
            ]
        ] = None,
        nested: bool = False,
        **kwargs: Dict[str, Any],
    ) -> T:
        cast_gen = self._solve(
            *args,
            cache_dependencies=cache_dependencies,
            dependency_overrides=dependency_overrides,
            **kwargs,
        )
        try:
            args, kwargs, _ = next(cast_gen)
        except StopIteration as e:
            cached_value: T = e.value
            return cached_value

        for dep in self.extra_dependencies:
            # TODO: run concurrently
            await dep.asolve(
                *args,
                stack=stack,
                cache_dependencies=cache_dependencies,
                dependency_overrides=dependency_overrides,
                nested=True,
                **kwargs,
            )

        for dep_arg, dep in self.dependencies.items():
            if dep_arg not in kwargs:
                kwargs[dep_arg] = await dep.asolve(
                    *args,
                    stack=stack,
                    cache_dependencies=cache_dependencies,
                    dependency_overrides=dependency_overrides,
                    nested=True,
                    **kwargs,
                )

        custom_to_solve: List[CustomField] = []

        try:
            async with anyio.create_task_group() as tg:
                for custom in self.custom_fields.values():
                    if custom.field:
                        tg.start_soon(run_async, custom.use_field, kwargs)
                    else:
                        custom_to_solve.append(custom)

        except ExceptionGroup as exgr:
            for ex in exgr.exceptions:
                raise ex from None

        for j in custom_to_solve:
            kwargs = await run_async(j.use, **kwargs)

        final_args, final_kwargs, call = cast_gen.send(kwargs)

        if self.is_generator and nested:
            response = await solve_generator_async(
                *final_args,
                call=call,
                stack=stack,
                **final_kwargs,
            )
        else:
            response = await run_async(call, *final_args, **final_kwargs)

        try:
            cast_gen.send(response)
        except StopIteration as e:
            value: T = e.value

            if self.caster is None or nested or not self.is_generator:
                return value

            else:
                return async_map(self._cast_response, value)  # type: ignore[return-value, arg-type]

        raise AssertionError("unreachable")
