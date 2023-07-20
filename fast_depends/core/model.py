import inspect
from contextlib import AsyncExitStack, ExitStack
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
    Tuple,
    Type,
    Union,
)

from typing_extensions import ParamSpec, TypeVar, assert_never

from fast_depends._compat import PYDANTIC_V2, BaseModel, FieldInfo
from fast_depends.library import CustomField
from fast_depends.utils import (
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
    call: Union[
        Callable[P, T],
        Callable[P, Awaitable[T]],
    ]
    is_async: bool
    is_generator: bool
    model: Type[BaseModel]
    response_model: Optional[Type[BaseModel]]

    params: Dict[str, FieldInfo]
    alias_arguments: List[str]

    dependencies: Dict[str, "CallModel[..., Any]"]
    extra_dependencies: Iterable["CallModel[..., Any]"]
    custom_fields: Dict[str, CustomField]
    keyword_args: Tuple[str]
    positional_args: Tuple[str]

    # Dependencies and custom fields
    use_cache: bool
    cast: bool

    __slots__ = (
        "call",
        "is_async",
        "is_generator",
        "model",
        "response_model",
        "params",
        "alias_arguments",
        "keyword_args",
        "positional_args",
        "dependencies",
        "extra_dependencies",
        "custom_fields",
        "use_cache",
        "cast",
    )

    @property
    def call_name(self) -> str:
        return getattr(self.call, "__name__", type(self.call).__name__)

    @property
    def real_params(self) -> Dict[str, FieldInfo]:
        params = self.params.copy()
        for name in self.custom_fields.keys():
            params.pop(name, None)
        return params

    @property
    def flat_params(self) -> Dict[str, FieldInfo]:
        params = self.real_params
        for d in self.dependencies.values():
            params.update(d.flat_params)
        return params

    def __init__(
        self,
        call: Union[
            Callable[P, T],
            Callable[P, Awaitable[T]],
        ],
        model: Type[BaseModel],
        response_model: Optional[Type[BaseModel]] = None,
        use_cache: bool = True,
        cast: bool = True,
        is_async: bool = False,
        dependencies: Optional[Dict[str, "CallModel[..., Any]"]] = None,
        extra_dependencies: Optional[Iterable["CallModel[..., Any]"]] = None,
        keyword_args: Optional[List[str]] = None,
        positional_args: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, CustomField]] = None,
    ):
        self.call = call
        self.model = model
        self.response_model = response_model

        fields: Dict[str, FieldInfo]
        if PYDANTIC_V2:
            fields = self.model.model_fields  # type: ignore
        else:
            fields = self.model.__fields__  # type: ignore

        self.dependencies = dependencies or {}
        self.extra_dependencies = extra_dependencies or []
        self.custom_fields = custom_fields or {}

        self.alias_arguments = [f.alias or name for name, f in fields.items()]
        self.keyword_args = tuple(keyword_args or [])
        self.positional_args = tuple(positional_args or [])

        self.params = fields.copy()
        for name in self.dependencies.keys():
            self.params.pop(name, None)

        self.use_cache = use_cache
        self.cast = cast
        self.is_async = is_async or is_coroutine_callable(call)
        self.is_generator = is_gen_callable(self.call) or is_async_gen_callable(
            self.call
        )

    def _solve(
        self,
        *args: P.args,
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
        **kwargs: P.kwargs,
    ) -> Generator[Dict[str, Any], Any, T]:
        if dependency_overrides:
            self.call = dependency_overrides.get(self.call, self.call)
            assert self.is_async or not is_coroutine_callable(
                self.call
            ), f"You cannot use async dependency `{self.call_name}` at sync main"

        if self.use_cache and self.call in cache_dependencies:
            return cache_dependencies[self.call]

        kw = {}

        for arg in self.keyword_args:
            v = kwargs.pop(arg, inspect._empty)
            if v is not inspect._empty:
                kw[arg] = v

        if "kwargs" in self.alias_arguments:
            kw["kwargs"] = kwargs

        else:
            kw.update(kwargs)

        has_args = "args" in self.alias_arguments

        for arg in self.positional_args:
            if args:
                kw[arg], args = args[0], args[1:]

        if has_args:
            kw["args"] = args

        else:
            for arg in self.keyword_args:
                if args:
                    kw[arg], args = args[0], args[1:]

        solved_kw: Dict[str, Any]
        solved_kw = yield kw

        casted_model = self.model(**solved_kw)

        kwargs_ = {
            arg: getattr(casted_model, arg, solved_kw.get(arg))
            for arg in (
                self.keyword_args + self.positional_args
                if not has_args
                else self.keyword_args
            )
        }
        kwargs_.update(getattr(casted_model, "kwargs", {}))

        if has_args:
            args_ = [
                getattr(casted_model, arg, solved_kw.get(arg))
                for arg in self.positional_args
            ]
            args_.extend(getattr(casted_model, "args", ()))
        else:
            args_ = ()

        response: T
        response = yield args_, kwargs_

        if self.cast is True and self.response_model is not None:
            casted_resp = self.response_model(response=response)
            response = casted_resp.response  # type: ignore

        if self.use_cache:  # pragma: no branch
            cache_dependencies[self.call] = response

        return response

    def solve(
        self,
        *args: P.args,
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
        **kwargs: P.kwargs,
    ) -> T:
        cast_gen = self._solve(
            *args,
            cache_dependencies=cache_dependencies,
            dependency_overrides=dependency_overrides,
            **kwargs,
        )
        try:
            kwargs = next(cast_gen)
        except StopIteration as e:
            cached_value: T = e.value
            return cached_value

        for dep in self.extra_dependencies:
            dep.solve(
                stack=stack,
                cache_dependencies=cache_dependencies,
                dependency_overrides=dependency_overrides,
                **kwargs,
            )

        for dep_arg, dep in self.dependencies.items():
            kwargs[dep_arg] = dep.solve(
                stack=stack,
                cache_dependencies=cache_dependencies,
                dependency_overrides=dependency_overrides,
                **kwargs,
            )

        for custom in self.custom_fields.values():
            kwargs = custom.use(**kwargs)

        final_args, final_kwargs = cast_gen.send(kwargs)

        if self.is_generator:
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
            value: T = e.value
            return value

        assert_never(response)  # pragma: no cover

    async def asolve(
        self,
        *args: P.args,
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
        **kwargs: P.kwargs,
    ) -> T:
        cast_gen = self._solve(
            *args,
            cache_dependencies=cache_dependencies,
            dependency_overrides=dependency_overrides,
            **kwargs,
        )
        try:
            kwargs = next(cast_gen)
        except StopIteration as e:
            cached_value: T = e.value
            return cached_value

        for dep in self.extra_dependencies:
            await dep.asolve(
                stack=stack,
                cache_dependencies=cache_dependencies,
                dependency_overrides=dependency_overrides,
                **kwargs,
            )

        for dep_arg, dep in self.dependencies.items():
            kwargs[dep_arg] = await dep.asolve(
                stack=stack,
                cache_dependencies=cache_dependencies,
                dependency_overrides=dependency_overrides,
                **kwargs,
            )

        for custom in self.custom_fields.values():
            kwargs = await run_async(custom.use, **kwargs)

        final_args, final_kwargs = cast_gen.send(kwargs)

        if self.is_generator:
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
            value: T = e.value
            return value

        assert_never(response)  # pragma: no cover
