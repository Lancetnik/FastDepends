from contextlib import AsyncExitStack, ExitStack
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Type,
    Union,
)

from typing_extensions import ParamSpec, TypeVar

from fast_depends._compat import PYDANTIC_V2, BaseModel
from fast_depends.library import CustomField
from fast_depends.utils import (
    args_to_kwargs,
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
    run_async,
    solve_generator_async,
    solve_generator_sync,
)

P = ParamSpec("P")
T = TypeVar("T")


class CallModel:
    call: Union[
        Callable[P, T],
        Callable[P, Awaitable[T]],
    ]
    is_async: bool
    is_generator: bool
    model: Type[BaseModel]
    response_model: Optional[Type[BaseModel]]
    arguments: List[str]
    alias_arguments: List[str]

    dependencies: Dict[str, "CallModel"]
    custom_fields: Dict[str, CustomField]

    # Dependencies and custom fields
    use_cache: bool
    cast: bool

    @property
    def call_name(self):
        return getattr(self.call, "__name__", type(self.call).__name__)

    @property
    def real_params(self) -> Set[str]:
        return set(self.arguments) - set(self.dependencies.keys())

    @property
    def flat_params(self) -> Set[str]:
        params = set(self.real_params)
        for d in self.dependencies.values():
            params |= set(d.flat_params)
        return params

    def __init__(
        self,
        call: Union[
            Callable[P, T],
            Callable[P, Awaitable[T]],
        ],
        model: BaseModel,
        response_model: Optional[Type[BaseModel]] = None,
        use_cache: bool = True,
        cast: bool = True,
        is_async: bool = False,
        dependencies: Optional[Dict[str, "CallModel"]] = None,
        custom_fields: Optional[Dict[str, CustomField]] = None,
    ):
        self.call = call
        self.model = model
        self.response_model = response_model

        self.arguments = []
        self.alias_arguments = []

        if PYDANTIC_V2:
            fields = self.model.model_fields
        else:  # pragma: no cover
            fields = self.model.__fields__

        for name, f in fields.items():
            self.arguments.append(name)
            self.alias_arguments.append(f.alias or name)

        self.dependencies = dependencies or {}
        self.custom_fields = custom_fields or {}

        self.use_cache = use_cache
        self.cast = cast
        self.is_async = is_async or is_coroutine_callable(call)
        self.is_generator = is_gen_callable(self.call) or is_async_gen_callable(
            self.call
        )

    def _cast_args(
        self,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Generator[Dict[str, Any], Any, T,]:
        kw = args_to_kwargs(self.alias_arguments, *args, **kwargs)

        kw_with_solved_dep = yield kw

        casted_model = self.model(**kw_with_solved_dep)

        casted_kw = {
            arg: getattr(casted_model, arg, kw_with_solved_dep.get(arg))
            for arg in (*self.arguments, *self.dependencies.keys())
        }

        response = yield casted_kw

        if self.cast is True and self.response_model is not None:
            casted_resp = self.response_model(response=response)
            response = casted_resp.response

        return response

    def solve(
        self,
        *args: P.args,
        stack: ExitStack,
        cache_dependencies: Dict[str, Any],
        dependency_overrides: Optional[Dict[Callable[..., Any], Any]] = None,
        **kwargs: P.kwargs,
    ) -> T:
        if dependency_overrides:
            self.call = dependency_overrides.get(self.call, self.call)
            assert not is_coroutine_callable(
                self.call
            ), f"You cannot use async dependency `{self.call_name}` at sync main"

        if self.use_cache and cache_dependencies.get(self.call):
            return cache_dependencies.get(self.call)

        cast_gen = self._cast_args(*args, **kwargs)
        kwargs = next(cast_gen)

        for dep_arg, dep in self.dependencies.items():
            kwargs[dep_arg] = dep.solve(
                stack=stack,
                cache_dependencies=cache_dependencies,
                dependency_overrides=dependency_overrides,
                **kwargs,
            )

        for custom in self.custom_fields.values():
            kwargs = custom.use(**kwargs)

        final_kw = cast_gen.send(kwargs)

        if self.is_generator:
            response = solve_generator_sync(
                call=self.call,
                stack=stack,
                **final_kw,
            )
        else:
            response = self.call(**final_kw)

        try:
            cast_gen.send(response)
        except StopIteration as e:
            if self.use_cache:  # pragma: no branch
                cache_dependencies[self.call] = e.value
            return e.value

    async def asolve(
        self,
        *args: P.args,
        stack: AsyncExitStack,
        cache_dependencies: Dict[str, Any],
        dependency_overrides: Optional[Dict[Callable[..., Any], Any]] = None,
        **kwargs: P.kwargs,
    ) -> T:
        if dependency_overrides:
            self.call = dependency_overrides.get(self.call, self.call)

        if self.use_cache and cache_dependencies.get(self.call):
            return cache_dependencies.get(self.call)

        cast_gen = self._cast_args(*args, **kwargs)
        kwargs = next(cast_gen)

        for dep_arg, dep in self.dependencies.items():
            kwargs[dep_arg] = await dep.asolve(
                stack=stack,
                cache_dependencies=cache_dependencies,
                dependency_overrides=dependency_overrides,
                **kwargs,
            )

        for custom in self.custom_fields.values():
            kwargs = await run_async(custom.use, **kwargs)

        final_kw = cast_gen.send(kwargs)

        if self.is_generator:
            response = await solve_generator_async(
                call=self.call,
                stack=stack,
                **final_kw,
            )
        else:
            response = await run_async(self.call, **final_kw)
        try:
            cast_gen.send(response)
        except StopIteration as e:
            if self.use_cache:  # pragma: no branch
                cache_dependencies[self.call] = e.value
            return e.value
