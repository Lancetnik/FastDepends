from collections.abc import Callable, Iterable, Mapping
from contextlib import AsyncExitStack, ExitStack
from inspect import Signature, unwrap
from typing import (
    TYPE_CHECKING,
    Any,
)

from fast_depends.library.model import CustomField
from fast_depends.library.serializer import OptionItem, Serializer, SerializerProto
from fast_depends.utils import (
    async_map,
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
    sync_map,
)

if TYPE_CHECKING:
    from fast_depends.core.preparation import Invocation, PreparedGraph, PreparedNode
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
        "serializer_cls",
        "_schema_custom_fields",
        "signature",
        "_options",
        "_prepared",
        "_prepared_key",
        "_extra_cache",
        "_is_sync",
    )

    alias_arguments: tuple[str, ...]
    _prepared: "PreparedGraph | None"
    _prepared_key: "tuple[int, Provider | None, int | None] | None"

    @property
    def call_name(self) -> str:
        call = unwrap(self.call)
        return getattr(call, "__name__", type(call).__name__)

    @property
    def flat_params(self) -> list[OptionItem]:
        return self.prepare().schema_options()

    def prepare(
        self, provider: "Provider | None" = None, *, force: bool = False
    ) -> "PreparedGraph":
        from fast_depends.core.preparation import PreparedGraph

        key = (
            self.dependency_provider.revision,
            provider,
            provider.revision if provider is not None else None,
        )
        prepared = self._prepared
        if force or self._prepared_key != key or prepared is None:
            prepared = PreparedGraph(self, provider)
            self._prepared = prepared
            self._prepared_key = key
        return prepared

    def __init__(
        self,
        *,
        call: Callable[..., Any],
        signature: Signature,
        options: list[OptionItem],
        serializer: Serializer | None,
        params: tuple[OptionItem, ...],
        use_cache: bool,
        is_async: bool,
        is_sync: bool,
        is_generator: bool,
        args_name: str | None,
        kwargs_name: str | None,
        dependencies: dict[str, "Key"],
        extra_dependencies: Iterable["Key"],
        extra_cache: tuple[bool, ...],
        keyword_args: list[str],
        positional_args: list[str],
        custom_fields: dict[str, CustomField],
        dependency_provider: "Provider",
        serializer_cls: SerializerProto | None,
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
            is_async or is_coroutine_callable(call) or is_async_gen_callable(call)
        )
        self._is_sync = is_sync
        self.is_generator = (
            is_generator or is_gen_callable(call) or is_async_gen_callable(call)
        )

        self.dependencies = dependencies or {}
        self.extra_dependencies = tuple(extra_dependencies or ())
        self._extra_cache = extra_cache
        self.custom_fields = custom_fields or {}

        self.params = params
        self.dependency_provider = dependency_provider
        self.serializer_cls = serializer_cls
        self._schema_custom_fields: tuple[OptionItem, ...] = ()

        self.signature = signature
        self._options = tuple(options)
        self._prepared = None
        self._prepared_key = None

    def _cast_response(self, value: Any) -> Any:
        if self.serializer is not None:
            return self.serializer.response(value)
        return value

    def solve(
        self,
        /,
        *args: Any,
        stack: ExitStack,
        cache_dependencies: dict[Callable[..., Any], Any],
        nested: bool = False,
        dependency_provider: "Provider | None" = None,
        arguments: tuple[tuple[Any, ...], dict[str, Any]] | None = None,
        context: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if arguments is not None:
            args, kwargs = arguments
        graph = self.prepare(dependency_provider)
        if graph.plain:
            args, kwargs = graph.plain_arguments(args, kwargs)
            if self.use_cache and self.call in cache_dependencies:
                return cache_dependencies[self.call]
            return self._call_sync(
                graph.nodes[self],
                args,
                kwargs,
                stack,
                cache_dependencies,
                nested,
                self.use_cache,
            )
        state = graph.bind(args, kwargs, context or {})
        return self._solve_sync(state, stack, cache_dependencies, nested)

    def _solve_sync(
        self,
        state: "Invocation",
        stack: ExitStack,
        cache: dict[Callable[..., Any], Any],
        nested: bool = True,
        use_cache: bool | None = None,
    ) -> Any:
        cache_enabled = self.use_cache if use_cache is None else use_cache
        if cache_enabled and self.call in cache:
            return cache[self.call]
        node = state.graph.nodes[self]
        dependencies: dict[str, Any] = {}
        for dependency, policy in node.extra_dependencies:
            dependency._solve_sync(state, stack, cache, use_cache=policy)
        for name, dependency, policy in node.dependencies:
            dependencies[name] = dependency._solve_sync(
                state, stack, cache, use_cache=policy
            )
        values = state.arguments(node)
        values.update(dependencies)
        for resolve, field_mode, contextual in node.custom_fields:
            previous = state.capture(node, values) if node.shared_bindings else None
            if contextual:
                values = resolve(state.framework_context, **values)
            elif field_mode:
                resolve(values)
            else:
                values = resolve(**values)
            if previous is not None:
                state.publish(node, previous, values)
        args, kwargs = state.resolve(node, values)
        return self._call_sync(node, args, kwargs, stack, cache, nested, cache_enabled)

    def _call_sync(
        self,
        node: "PreparedNode",
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        stack: ExitStack,
        cache: dict[Callable[..., Any], Any],
        nested: bool,
        cache_enabled: bool,
    ) -> Any:
        if self.is_generator and nested:
            assert node.context is not None
            result = stack.enter_context(node.context(*args, **kwargs))
        else:
            result = self.call(*args, **kwargs)
        if not self.is_generator:
            result = self._cast_response(result)
        elif not nested and self.serializer is not None:
            result = sync_map(self._cast_response, result)
        if cache_enabled:
            cache[self.call] = result
        return result

    async def asolve(
        self,
        /,
        *args: Any,
        stack: AsyncExitStack,
        cache_dependencies: dict[Callable[..., Any], Any],
        nested: bool = False,
        dependency_provider: "Provider | None" = None,
        arguments: tuple[tuple[Any, ...], dict[str, Any]] | None = None,
        context: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if arguments is not None:
            args, kwargs = arguments
        graph = self.prepare(dependency_provider)
        if graph.plain:
            args, kwargs = graph.plain_arguments(args, kwargs)
            if self.use_cache and self.call in cache_dependencies:
                return cache_dependencies[self.call]
            return await self._call_async(
                graph.nodes[self],
                args,
                kwargs,
                stack,
                cache_dependencies,
                nested,
                self.use_cache,
            )
        state = graph.bind(args, kwargs, context or {})
        return await self._solve_async(state, stack, cache_dependencies, nested)

    async def _solve_async(
        self,
        state: "Invocation",
        stack: AsyncExitStack,
        cache: dict[Callable[..., Any], Any],
        nested: bool = True,
        use_cache: bool | None = None,
    ) -> Any:
        cache_enabled = self.use_cache if use_cache is None else use_cache
        if cache_enabled and self.call in cache:
            return cache[self.call]
        node = state.graph.nodes[self]
        dependencies: dict[str, Any] = {}
        for dependency, policy in node.extra_dependencies:
            await dependency._solve_async(state, stack, cache, use_cache=policy)
        for name, dependency, policy in node.dependencies:
            dependencies[name] = await dependency._solve_async(
                state, stack, cache, use_cache=policy
            )
        values = state.arguments(node)
        values.update(dependencies)
        for resolve, field_mode, contextual in node.async_custom_fields:
            previous = state.capture(node, values) if node.shared_bindings else None
            if contextual:
                values = await resolve(state.framework_context, **values)
            elif field_mode:
                await resolve(values)
            else:
                values = await resolve(**values)
            if previous is not None:
                state.publish(node, previous, values)
        args, kwargs = state.resolve(node, values)
        return await self._call_async(
            node, args, kwargs, stack, cache, nested, cache_enabled
        )

    async def _call_async(
        self,
        node: "PreparedNode",
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        stack: AsyncExitStack,
        cache: dict[Callable[..., Any], Any],
        nested: bool,
        cache_enabled: bool,
    ) -> Any:
        if self.is_generator and nested:
            assert node.async_context is not None
            result = await stack.enter_async_context(node.async_context(*args, **kwargs))
        else:
            result = await node.async_call(*args, **kwargs)
        if not self.is_generator:
            result = self._cast_response(result)
        elif not nested and self.serializer is not None:
            result = async_map(self._cast_response, result)
        if cache_enabled:
            cache[self.call] = result
        return result
