from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    asynccontextmanager,
    contextmanager,
)
from copy import copy
from inspect import Parameter
from types import MethodType
from typing import TYPE_CHECKING, Any, cast, get_args, get_origin

from fast_depends.library.model import CustomField
from fast_depends.library.schema import SchemaField
from fast_depends.library.serializer import (
    InputField,
    OptionItem,
    PreparedInputs,
    PreparedValue,
    Serializer,
)
from fast_depends.utils import (
    _prepare_async_call,
    contextmanager_in_threadpool,
    is_gen_callable,
)

if TYPE_CHECKING:
    from fast_depends.core.model import CallModel
    from fast_depends.dependencies.provider import Provider

_MISSING = object()


def _same_contract(left: Any, right: Any) -> bool:
    if left is right:
        return True
    origin = get_origin(left)
    if origin is not None or get_origin(right) is not None:
        return origin is get_origin(right) and _same_contract(
            get_args(left), get_args(right)
        )
    if type(left) is not type(right):
        return False
    if type(left) in (str, bytes, int, float, bool, type(None)):
        return bool(left == right)
    if type(left) in (tuple, list):
        return len(left) == len(right) and all(
            _same_contract(a, b) for a, b in zip(left, right, strict=True)
        )
    if type(left) is dict:
        return left.keys() == right.keys() and all(
            _same_contract(left[key], right[key]) for key in left
        )
    if isinstance(left, MethodType) and isinstance(right, MethodType):
        return left.__func__ is right.__func__ and left.__self__ is right.__self__
    return False


class PreparedNode:
    __slots__ = (
        "model",
        "fields",
        "dependencies",
        "extra_dependencies",
        "parameters",
        "keyword_names",
        "keyword_only_call",
        "custom_fields",
        "async_custom_fields",
        "async_call",
        "context",
        "async_context",
        "shared_bindings",
        "nested_bindings",
        "validate",
    )

    def __init__(self, model: CallModel, fields: dict[str, InputField]) -> None:
        self.model = model
        self.fields = fields
        self.dependencies: tuple[tuple[str, CallModel, bool], ...] = ()
        self.extra_dependencies: tuple[tuple[CallModel, bool], ...] = ()
        self.custom_fields: tuple[tuple[Callable[..., Any], bool, bool], ...] = tuple(
            (custom.resolve, False, True)
            if type(custom).resolve is not CustomField.resolve
            else (custom.use_field if custom.field else custom.use, custom.field, False)
            for custom in model.custom_fields.values()
        )
        self.async_custom_fields = tuple(
            (_prepare_async_call(resolve), field_mode, contextual)
            for resolve, field_mode, contextual in self.custom_fields
        )
        self.async_call = _prepare_async_call(model.call)
        self.context: Callable[..., AbstractContextManager[Any]] | None = None
        self.async_context: Callable[..., AbstractAsyncContextManager[Any]] | None = None
        if model.is_generator:
            if is_gen_callable(model.call):
                context = self.context = contextmanager(model.call)

                def async_context(
                    *args: Any, **kwargs: Any
                ) -> AbstractAsyncContextManager[Any]:
                    return contextmanager_in_threadpool(context(*args, **kwargs))

                self.async_context = async_context
            else:
                self.async_context = asynccontextmanager(model.call)
        self.shared_bindings: tuple[tuple[Hashable, tuple[str | int, ...]], ...] = ()
        self.nested_bindings: tuple[tuple[Hashable, tuple[str | int, ...]], ...] = ()
        self.validate: Callable[[dict[str, Any]], dict[str, Any]] | None = None
        self.parameters = tuple(model.signature.parameters.values())
        self.keyword_names = tuple(parameter.name for parameter in self.parameters)
        self.keyword_only_call = (
            not model.args_name
            and not model.kwargs_name
            and all(
                parameter.kind is not Parameter.POSITIONAL_ONLY
                for parameter in self.parameters
            )
        )

    def split(self, values: dict[str, Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
        if self.keyword_only_call:
            return (), {
                name: values[name] for name in self.keyword_names if name in values
            }
        args: list[Any] = []
        kwargs: dict[str, Any] = {}
        for parameter in self.parameters:
            name = parameter.name
            if parameter.kind is Parameter.VAR_POSITIONAL:
                args.extend(values.get(name, ()))
            elif parameter.kind is Parameter.VAR_KEYWORD:
                kwargs.update(values.get(name, {}))
            elif name in values:
                if (
                    parameter.kind is Parameter.POSITIONAL_ONLY
                    or self.model.args_name
                    and parameter.kind is Parameter.POSITIONAL_OR_KEYWORD
                ):
                    args.append(values[name])
                else:
                    kwargs[name] = values[name]
        return tuple(args), kwargs


class PreparedGraph:
    def __init__(self, root: CallModel, provider: Provider | None) -> None:
        self.root = root
        self.parameters = tuple(root.signature.parameters.values())
        self.nodes: dict[CallModel, PreparedNode] = {}
        self.fields: dict[Hashable, InputField] = {}
        self.names: dict[str, Hashable] = {}
        self.injected: set[str] = set()
        self._declarations: dict[Hashable, str] = {}
        self._schema_overrides: set[Hashable] = set()
        paths: dict[tuple[str | int, ...], Hashable] = {}
        prefixes: dict[tuple[str | int, ...], Hashable] = {}
        effective = dict(root.dependency_provider.dependencies)
        effective.update(root.dependency_provider.overrides)
        if provider is not None and provider is not root.dependency_provider:
            effective.update(provider.dependencies)
            effective.update(provider.overrides)

        def visit(model: CallModel, active: frozenset[CallModel]) -> None:
            if model in active:
                raise ValueError(f"Dependency cycle involving {model.call_name}")
            if model in self.nodes:
                return
            if root.serializer is None and model.serializer is not None and model.params:
                raise TypeError(
                    f"Validated inputs from {model.call_name} require a root serializer"
                )
            if model.serializer is not None:
                for method in ("prepare_fields", "prepare_inputs", "validate_resolved"):
                    if getattr(type(model.serializer), method) is getattr(
                        Serializer, method
                    ):
                        raise TypeError(
                            f"{type(model.serializer).__name__} does not support staged input validation: {method}"
                        )
            fields = (
                model.serializer.prepare_fields()
                if model.serializer is not None
                else {
                    option.field_name: InputField(
                        option,
                        key=(option.source, option.field_name),
                        paths=((option.field_name,),),
                        required=option.default_value is Ellipsis,
                        contract=option.field_type,
                        schema=None,
                    )
                    for option in model.params
                }
            )
            node = self.nodes[model] = PreparedNode(model, fields)
            for name, field in fields.items():
                if not field.paths or any(
                    not path or not isinstance(path[0], str) for path in field.paths
                ):
                    raise TypeError("An external input alias must start with a name")
                declaration = f"{model.call_name}.{name}"
                if field.key in self.fields:
                    current = self.fields[field.key]
                    if not _same_contract(current.contract, field.contract):
                        raise TypeError(
                            f"Incompatible input declarations: "
                            f"{self._declarations[field.key]} and {declaration}"
                        )
                    if current.required != field.required or not _same_contract(
                        current.option.default_value, field.option.default_value
                    ):
                        self._schema_overrides.add(field.key)
                    current.required |= field.required
                    current.paths += tuple(
                        p for p in field.paths if p not in current.paths
                    )
                else:
                    self.fields[field.key] = copy(field)
                    self._declarations[field.key] = declaration
                for path in field.paths:
                    overlap = next(
                        (
                            paths[path[:i]]
                            for i in range(1, len(path))
                            if path[:i] in paths
                        ),
                        prefixes.get(path, _MISSING),
                    )
                    if overlap is not _MISSING:
                        raise TypeError(
                            f"Overlapping input paths: {self._declarations[overlap]} "
                            f"and {declaration} ({path!r})"
                        )
                    previous = paths.setdefault(path, field.key)
                    if previous != field.key:
                        raise TypeError(
                            f"Ambiguous external input {path!r}: "
                            f"{self._declarations[previous]} and {declaration}"
                        )
                    for i in range(1, len(path)):
                        prefixes.setdefault(path[:i], field.key)
                    if len(path) == 1 and isinstance(path[0], str):
                        self.names[path[0]] = field.key
            self.injected.update(model.dependencies)
            policies = {
                option.field_name: option.source.use_cache
                for option in model._options
                if option.field_name in model.dependencies
            }
            node.dependencies = tuple(
                (name, effective[key], policies[name])
                for name, key in model.dependencies.items()
            )
            node.extra_dependencies = tuple(
                (effective[key], policy)
                for key, policy in zip(
                    model.extra_dependencies, model._extra_cache, strict=True
                )
            )
            for child in (
                *(m for _, m, _ in node.dependencies),
                *(m for m, _ in node.extra_dependencies),
            ):
                if root._is_sync and child.is_async:
                    raise TypeError("An async dependency cannot be used by a sync call")
                visit(child, active | {model})

        visit(root, frozenset())
        for node in self.nodes.values():
            if node.custom_fields:
                blocked = node.model.dependencies.keys() | node.model.custom_fields.keys()
                bindings = [
                    (field.key, path)
                    for field in self.fields.values()
                    for path in field.paths
                    if path[0] not in blocked
                ]
                bindings.extend(
                    (field.key, (name,)) for name, field in node.fields.items()
                )
                node.shared_bindings = tuple(dict.fromkeys(bindings))
                node.nested_bindings = tuple(
                    (key, path) for key, path in node.shared_bindings if len(path) > 1
                )
        self.plain = (
            not root.dependencies
            and not root.extra_dependencies
            and not root.custom_fields
            and len(self.fields) == len(self.nodes[root].fields)
        )
        self.injected.difference_update(
            path[0] for field in self.fields.values() for path in field.paths
        )
        positionals = []
        for parameter in self.parameters:
            if parameter.kind not in (
                Parameter.POSITIONAL_ONLY,
                Parameter.POSITIONAL_OR_KEYWORD,
            ):
                continue
            field = self.nodes[root].fields.get(parameter.name)
            if field is None and parameter.name in self.names:
                field = self.fields[self.names[parameter.name]]
            positionals.append(
                (parameter.name, field.paths if field else ((parameter.name,),))
            )
        self.positionals = tuple(positionals)
        self.positional_only = frozenset(
            parameter.name
            for parameter in self.parameters
            if parameter.kind is Parameter.POSITIONAL_ONLY
            and parameter.name in self.nodes[root].fields
        )
        self.simple_positionals = (
            tuple(cast(str, paths[0][0]) for _, paths in positionals)
            if all(len(paths) == 1 and len(paths[0]) == 1 for _, paths in positionals)
            else None
        )
        self.keyword_consumed = (
            {
                str(path[0])
                for field in self.nodes[root].fields.values()
                if field.option.kind is not Parameter.VAR_KEYWORD
                for path in field.paths
            }
            | set(root.dependencies)
            | set(root.custom_fields)
        )
        self.validate_plain: Callable[[dict[str, Any]], dict[str, Any]] | None = None
        self.validate_inputs: PreparedInputs | None = None
        if self.plain:
            if root.serializer is not None:
                self.validate_plain = root.serializer._prepare_call(staged=False)
        elif root.serializer is None:
            self.validate_inputs = self._unvalidated_inputs
        else:
            self.validate_inputs = root.serializer.prepare_inputs(
                tuple(self.fields.values())
            )
        if not self.plain:
            for node in self.nodes.values():
                if node.model.serializer is not None:
                    node.validate = node.model.serializer._prepare_call(staged=True)

    def schema_options(self) -> list[OptionItem]:
        return [
            SchemaField(
                field.schema_option.field_name,
                field.schema_option.field_type,
                default_value=field.schema_option.default_value,
                required=field.required,
            )
            if field.key in self._schema_overrides
            else field.option
            for field in self.fields.values()
        ]

    def _unvalidated_inputs(self, raw: dict[str, Any]) -> dict[Hashable, PreparedValue]:
        for field in self.fields.values():
            if field.required and field.paths[0][0] not in raw:
                raise TypeError(f"Missing required argument {field.option.field_name!r}")
        return {
            field.key: PreparedValue(raw[field.paths[0][0]])
            for field in self.fields.values()
            if field.paths[0][0] in raw
        }

    def bind_arguments(
        self, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        raw = kwargs.copy()
        count = len(args)
        positional_count = len(self.positionals)
        positional_extras = {
            name: raw.pop(name) for name in self.positional_only if name in raw
        }
        if positional_extras and not self.root.kwargs_name:
            raise TypeError(
                f"Positional-only argument passed by keyword: {next(iter(positional_extras))!r}"
            )
        if count > positional_count and not self.root.args_name:
            raise TypeError(f"Too many positional arguments for {self.root.call_name}")
        if self.simple_positionals is not None:
            for name, value in zip(self.simple_positionals, args, strict=False):
                if name in raw:
                    raise TypeError(f"Multiple values for argument {name!r}")
                raw[name] = value
        else:
            for index, (name, paths) in enumerate(self.positionals):
                if index == count:
                    break
                if any(_path_present(raw, path) for path in paths):
                    raise TypeError(f"Multiple values for argument {name!r}")
                _bind_path(raw, paths[0], args[index])
        if self.root.args_name:
            raw[self.root.args_name] = args[positional_count:]
        if self.injected:
            forbidden = self.injected.intersection(raw)
            if forbidden:
                raise TypeError(
                    f"Cannot supply injected dependency {sorted(forbidden)[0]!r}"
                )
        if self.root.kwargs_name:
            raw[self.root.kwargs_name] = {
                k: v for k, v in raw.items() if k not in self.keyword_consumed
            } | positional_extras
        return raw

    def bind(
        self, args: tuple[Any, ...], kwargs: dict[str, Any], context: Mapping[str, Any]
    ) -> Invocation:
        raw = self.bind_arguments(args, kwargs)
        assert self.validate_inputs is not None
        values = self.validate_inputs(raw)
        return Invocation(self, values, {**context, **raw}, context)

    def plain_arguments(
        self, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        values = self.bind_arguments(args, kwargs)
        if self.validate_plain is not None:
            values = self.validate_plain(values)
        return self.nodes[self.root].split(values)


def _bind_path(raw: dict[str, Any], path: tuple[str | int, ...], value: Any) -> None:
    current: Any = raw
    for index, name in enumerate(path):
        final = index == len(path) - 1
        if isinstance(current, list) and isinstance(name, int):
            size = name + 1 if name >= 0 else -name
            if len(current) < size:
                current.extend([None] * (size - len(current)))
        if final:
            current[name] = value
        else:
            if not _path_present(current, (name,)) or current[name] is None:
                current[name] = [] if isinstance(path[index + 1], int) else {}
            elif isinstance(current[name], dict):
                current[name] = dict.copy(current[name])
            elif isinstance(current[name], list):
                current[name] = list.copy(current[name])
            current = current[name]


def _path_present(raw: Any, path: tuple[str | int, ...]) -> bool:
    return _path_value(raw, path) is not _MISSING


def _path_value(raw: Any, path: tuple[str | int, ...]) -> Any:
    try:
        for name in path:
            raw = raw[name]
    except (KeyError, IndexError, TypeError):
        return _MISSING
    return raw


class Invocation:
    __slots__ = ("graph", "values", "context", "framework_context")

    def __init__(
        self,
        graph: PreparedGraph,
        values: dict[Hashable, PreparedValue],
        context: dict[str, Any],
        framework_context: Mapping[str, Any],
    ) -> None:
        self.graph = graph
        self.values = values
        self.context = context
        self.framework_context = framework_context

    def arguments(self, node: PreparedNode) -> dict[str, Any]:
        if not node.model.custom_fields:
            return {
                name: self.values[field.key]
                for name, field in node.fields.items()
                if field.key in self.values
            }
        values = self.context.copy()
        for name in node.fields:
            values.pop(name, None)
        self.refresh(node, values)
        return values

    def refresh(self, node: PreparedNode, values: dict[str, Any]) -> None:
        injected = node.model.dependencies.keys() | node.model.custom_fields.keys()
        for name, key in self.graph.names.items():
            if name not in injected and name not in node.fields and key in self.values:
                values[name] = self.values[key].value
        for key, path in node.nested_bindings:
            if key in self.values:
                _bind_path(values, path, self.values[key].value)
        for name, field in node.fields.items():
            if field.key in self.values:
                values[name] = self.values[field.key].value
            else:
                values.pop(name, None)

    def capture(self, node: PreparedNode, values: dict[str, Any]) -> list[Any]:
        return [_path_value(values, path) for _, path in node.shared_bindings]

    def publish(
        self, node: PreparedNode, previous: list[Any], values: dict[str, Any]
    ) -> None:
        for (key, path), before in zip(node.shared_bindings, previous, strict=True):
            after = _path_value(values, path)
            if after is before:
                continue
            if after is _MISSING:
                self.values.pop(key, None)
            elif key in self.values:
                self.values[key].value = after
            else:
                self.values[key] = PreparedValue(after)
        self.refresh(node, values)

    def resolve(
        self, node: PreparedNode, values: dict[str, Any]
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        model = node.model
        if model.custom_fields:
            for name, field in node.fields.items():
                if field.key in self.values:
                    values[name] = self.values[field.key]
                else:
                    values.pop(name, None)
            values = {
                option.field_name: values[option.field_name]
                for option in model._options
                if option.field_name in values
            }
        if node.validate is not None:
            values = node.validate(values)
        else:
            values = values.copy()
            for name, value in values.items():
                if isinstance(value, PreparedValue):
                    values[name] = value.value
            for option in model._options:
                if (
                    option.field_name not in values
                    and option.default_value is not Ellipsis
                ):
                    values[option.field_name] = option.default_value
        return node.split(values)
