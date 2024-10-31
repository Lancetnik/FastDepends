from collections.abc import Generator, Iterable, Sequence
from contextlib import AsyncExitStack, ExitStack
from inspect import Parameter, unwrap
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
)

import anyio

from fast_depends._compat import ExceptionGroup
from fast_depends.library.model import CustomField
from fast_depends.library.serializer import OptionItem, Serializer
from fast_depends.utils import (
    async_map,
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
    run_async,
    solve_generator_async,
    solve_generator_sync,
)

if TYPE_CHECKING:
    from fast_depends.dependencies.provider import Key, Provider


class CallModel:
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
        "serializer",
        "dependency_provider",
    )

    alias_arguments: tuple[str, ...]

    @property
    def call_name(self) -> str:
        call = unwrap(self.call)
        return getattr(call, "__name__", type(call).__name__)

    @property
    def flat_params(self) -> list[OptionItem]:
        params = list(self.params)
        for d in map(
            self.dependency_provider.get_dependant,
            (*self.dependencies.values(), *self.extra_dependencies),
        ):
            for p in d.flat_params:
                if p.field_name not in (i.field_name for i in params):
                    params.append(p)
        return params

    def __init__(
        self,
        *,
        call: Callable[..., Any],
        serializer: Optional[Serializer],
        params: tuple[OptionItem, ...],
        use_cache: bool,
        is_async: bool,
        is_generator: bool,
        args_name: Optional[str],
        kwargs_name: Optional[str],
        dependencies: dict[str, "Key"],
        extra_dependencies: Iterable["Key"],
        keyword_args: list[str],
        positional_args: list[str],
        custom_fields: dict[str, CustomField],
        dependency_provider: "Provider",
    ):
        self.call = call
        self.serializer = serializer

        if serializer is not None:
            self.alias_arguments = serializer.get_aliases()
        else:  # pragma: no cover
            self.alias_arguments = ()

        self.args_name = args_name
        self.keyword_args = tuple(keyword_args or ())
        self.kwargs_name = kwargs_name
        self.positional_args = tuple(positional_args or ())

        self.use_cache = use_cache
        self.is_async = (
            is_async or
            is_coroutine_callable(call) or
            is_async_gen_callable(call)
        )
        self.is_generator = (
            is_generator or
            is_gen_callable(call) or
            is_async_gen_callable(call)
        )

        self.dependencies = dependencies or {}
        self.extra_dependencies = tuple(extra_dependencies or ())
        self.custom_fields = custom_fields or {}

        self.params = params
        self.dependency_provider = dependency_provider

    def _solve(
        self,
        /,
        *args: tuple[Any, ...],
        cache_dependencies: dict[Callable[..., Any], Any],
        **kwargs: dict[str, Any],
    ) -> Generator[
        tuple[
            Sequence[Any],
            dict[str, Any],
        ],
        Any,
        Any,
    ]:
        if self.use_cache and self.call in cache_dependencies:
            return cache_dependencies[self.call]

        kw: dict[str, Any] = {}
        for arg in self.keyword_args:
            if (v := kwargs.pop(arg, Parameter.empty)) is not Parameter.empty:
                kw[arg] = v

        if self.kwargs_name in self.alias_arguments:
            kw[self.kwargs_name] = kwargs
        else:
            kw.update(kwargs)

        for arg in self.positional_args:
            if arg not in kw:
                if args:
                    kw[arg], args = args[0], args[1:]
                else:
                    break

        keyword_args: Iterable[str]
        if self.args_name in self.alias_arguments:
            kw[self.args_name] = args
            keyword_args = self.keyword_args

        else:
            keyword_args = self.keyword_args + self.positional_args
            for arg in keyword_args:
                if not args:
                    break

                if arg not in self.dependencies and arg not in kw:
                    kw[arg], args = args[0], args[1:]

        solved_kw: dict[str, Any]
        solved_kw = yield args, kw

        args_: Sequence[Any]
        if self.serializer is not None:
            casted_options = self.serializer(solved_kw)
            solved_kw.update(casted_options)

        if self.args_name:
            args_ = (
                *map(solved_kw.pop, self.positional_args),
                *solved_kw.get(self.args_name, args),
            )
        else:
            args_ = ()

        kwargs_ = {
            arg: solved_kw.pop(arg)
            for arg in keyword_args
            if arg in solved_kw
        }
        if self.kwargs_name:
            kwargs_.update(solved_kw.get(self.kwargs_name, solved_kw))

        response = yield args_, kwargs_

        if not self.is_generator:
            response = self._cast_response(response)

        if self.use_cache:  # pragma: no branch
            cache_dependencies[self.call] = response

        return response

    def _cast_response(self, /, value: Any) -> Any:
        if self.serializer is not None:
            return self.serializer.response(value)
        return value

    def solve(
        self,
        /,
        *args: tuple[Any, ...],
        stack: ExitStack,
        cache_dependencies: dict[Callable[..., Any], Any],
        nested: bool = False,
        **kwargs: dict[str, Any],
    ) -> Any:
        cast_gen = self._solve(
            *args,
            cache_dependencies=cache_dependencies,
            **kwargs,
        )
        try:
            args, kwargs = next(cast_gen)
        except StopIteration as e:
            cached_value = e.value
            return cached_value

        for dep in map(self.dependency_provider.get_dependant, self.extra_dependencies):
            dep.solve(
                *args,
                stack=stack,
                cache_dependencies=cache_dependencies,
                nested=True,
                **kwargs,
            )

        for dep_arg, dep_key in self.dependencies.items():
            if dep_arg not in kwargs:
                kwargs[dep_arg] = self.dependency_provider.get_dependant(dep_key).solve(
                    *args,
                    stack=stack,
                    cache_dependencies=cache_dependencies,
                    nested=True,
                    **kwargs,
                )

        for custom in self.custom_fields.values():
            if custom.field:
                custom.use_field(kwargs)
            else:
                kwargs = custom.use(**kwargs)

        final_args, final_kwargs = cast_gen.send(kwargs)

        if self.is_generator and nested:
            response = solve_generator_sync(
                *final_args,
                call=self.call,
                stack=stack,
                **final_kwargs,
            )

        else:
            response = self.call(*final_args, **final_kwargs)

        try:
            cast_gen.send(response)
        except StopIteration as e:
            value = e.value

            if self.serializer is None or nested or not self.is_generator:
                return value

            else:
                return map(self._cast_response, value)

        raise AssertionError("unreachable")

    async def asolve(
        self,
        /,
        *args: tuple[Any, ...],
        stack: AsyncExitStack,
        cache_dependencies: dict[Callable[..., Any], Any],
        nested: bool = False,
        **kwargs: dict[str, Any],
    ) -> Any:
        cast_gen = self._solve(
            *args,
            cache_dependencies=cache_dependencies,
            **kwargs,
        )
        try:
            args, kwargs = next(cast_gen)
        except StopIteration as e:
            cached_value = e.value
            return cached_value

        for dep in map(self.dependency_provider.get_dependant, self.extra_dependencies):
            # TODO: run concurrently
            await dep.asolve(
                *args,
                stack=stack,
                cache_dependencies=cache_dependencies,
                nested=True,
                **kwargs,
            )

        for dep_arg, dep_key in self.dependencies.items():
            if dep_arg not in kwargs:
                kwargs[dep_arg] = await self.dependency_provider.get_dependant(dep_key).asolve(
                    *args,
                    stack=stack,
                    cache_dependencies=cache_dependencies,
                    nested=True,
                    **kwargs,
                )

        custom_to_solve: list[CustomField] = []

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

        final_args, final_kwargs = cast_gen.send(kwargs)

        if self.is_generator and nested:
            response = await solve_generator_async(
                *final_args,
                call=self.call,
                stack=stack,
                **final_kwargs,
            )
        else:
            response = await run_async(self.call, *final_args, **final_kwargs)

        try:
            cast_gen.send(response)
        except StopIteration as e:
            value = e.value

            if self.serializer is None or nested or not self.is_generator:
                return value

            else:
                return async_map(self._cast_response, value)

        raise AssertionError("unreachable")
