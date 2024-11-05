import inspect
from collections.abc import Sequence
from copy import deepcopy
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Optional,
    TypeVar,
)

from typing_extensions import (
    ParamSpec,
    get_args,
    get_origin,
)

from fast_depends.dependencies.model import Dependant
from fast_depends.library import CustomField
from fast_depends.library.serializer import OptionItem, Serializer, SerializerProto
from fast_depends.utils import (
    get_typed_signature,
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
)

from .model import CallModel

if TYPE_CHECKING:
    from fast_depends.dependencies.provider import Key, Provider


CUSTOM_ANNOTATIONS = (Dependant, CustomField,)


P = ParamSpec("P")
T = TypeVar("T")


def build_call_model(
    call: Callable[..., Any],
    *,
    dependency_provider: "Provider",
    use_cache: bool = True,
    is_sync: Optional[bool] = None,
    extra_dependencies: Sequence[Dependant] = (),
    serializer_cls: Optional["SerializerProto"] = None,
    serialize_result: bool = True,
) -> CallModel:
    name = getattr(inspect.unwrap(call), "__name__", type(call).__name__)

    is_call_async = is_coroutine_callable(call) or is_async_gen_callable(call)
    if is_sync is None:
        is_sync = not is_call_async
    else:
        assert not (
            is_sync and is_call_async
        ), f"You cannot use async dependency `{name}` at sync main"

    typed_params, return_annotation = get_typed_signature(call)
    if (
        (is_call_generator := is_gen_callable(call) or
        is_async_gen_callable(call)) and
        (return_args := get_args(return_annotation))
    ):
        return_annotation = return_args[0]

    if not serialize_result:
        return_annotation = inspect.Parameter.empty

    class_fields: list[OptionItem] = []
    dependencies: dict[str, Key] = {}
    custom_fields: dict[str, CustomField] = {}
    positional_args: list[str] = []
    keyword_args: list[str] = []
    args_name: Optional[str] = None
    kwargs_name: Optional[str] = None

    for param_name, param in typed_params.parameters.items():
        dep: Optional[Dependant] = None
        custom: Optional[CustomField] = None

        if param.annotation is inspect.Parameter.empty:
            annotation = Any

        elif get_origin(param.annotation) is Annotated:
            annotated_args = get_args(param.annotation)
            type_annotation = annotated_args[0]

            custom_annotations = []
            regular_annotations = []
            for arg in annotated_args[1:]:
                if isinstance(arg, CUSTOM_ANNOTATIONS):
                    custom_annotations.append(arg)
                else:
                    regular_annotations.append(arg)

            assert (
                len(custom_annotations) <= 1
            ), f"Cannot specify multiple `Annotated` Custom arguments for `{param_name}`!"

            next_custom = next(iter(custom_annotations), None)
            if next_custom is not None:
                if isinstance(next_custom, Dependant):
                    dep = next_custom
                elif isinstance(next_custom, CustomField):
                    custom = deepcopy(next_custom)
                else:  # pragma: no cover
                    raise AssertionError("unreachable")

                if regular_annotations:
                    annotation = param.annotation
                else:
                    annotation = type_annotation
            else:
                annotation = param.annotation
        else:
            annotation = param.annotation

        default: Any
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            default = ()
        elif param.kind is inspect.Parameter.VAR_KEYWORD:
            default = {}
        else:
            default = param.default

        if isinstance(default, Dependant):
            assert (
                not dep
            ), "You can not use `Depends` with `Annotated` and default both"
            dep, default = default, Ellipsis

        elif isinstance(default, CustomField):
            assert (
                not custom
            ), "You can not use `CustomField` with `Annotated` and default both"
            custom, default = default, Ellipsis

        elif not dep and not custom:
            class_fields.append(OptionItem(
                field_name=param_name,
                field_type=annotation,
                default_value=... if default is inspect.Parameter.empty else default
            ))

        if dep:
            dependency = build_call_model(
                dep.dependency,
                dependency_provider=dependency_provider,
                use_cache=dep.use_cache,
                is_sync=is_sync,
                serializer_cls=serializer_cls,
                serialize_result=dep.cast_result,
            )

            key = dependency_provider.add_dependant(dependency)

            overrided_dependency = dependency_provider.get_dependant(key)

            assert not (
                is_sync and is_coroutine_callable(overrided_dependency.call)
            ), f"You cannot use async dependency `{overrided_dependency.call_name}` at sync main"

            dependencies[param_name] = key

            if not dep.cast:
                annotation = Any

            class_fields.append(OptionItem(
                field_name=param_name,
                field_type=annotation,
                source=dep,
            ))

            keyword_args.append(param_name)

        elif custom:
            assert not (
                is_sync and is_coroutine_callable(custom.use)
            ), f"You cannot use async custom field `{type(custom).__name__}` at sync `{name}`"

            custom.set_param_name(param_name)
            custom_fields[param_name] = custom

            if not custom.cast:
                annotation = Any

            if custom.required:
                class_fields.append(OptionItem(
                    field_name=param_name,
                    field_type=annotation,
                    default_value=default,
                    source=custom,
                ))

            else:
                class_fields.append(OptionItem(
                    field_name=param_name,
                    field_type=Optional[annotation],
                    default_value=None if default is Ellipsis else default,
                    source=custom,
                ))

            keyword_args.append(param_name)

        else:
            if param.kind is param.KEYWORD_ONLY:
                keyword_args.append(param_name)
            elif param.kind is param.VAR_KEYWORD:
                kwargs_name = param_name
            elif param.kind is param.VAR_POSITIONAL:
                args_name = param_name
            else:
                positional_args.append(param_name)

    serializer: Optional[Serializer] = None
    if serializer_cls is not None:
        serializer = serializer_cls(
            name=name,
            options=class_fields,
            response_type=return_annotation,
        )

    solved_extra_dependencies: list[Key] = []
    for dep in extra_dependencies:
        dependency = build_call_model(
            dep.dependency,
            dependency_provider=dependency_provider,
            use_cache=dep.use_cache,
            is_sync=is_sync,
            serializer_cls=serializer_cls,
        )

        key = dependency_provider.add_dependant(dependency)

        overrided_dependency = dependency_provider.get_dependant(key)

        assert not (
            is_sync and is_coroutine_callable(overrided_dependency.call)
        ), f"You cannot use async dependency `{overrided_dependency.call_name}` at sync main"

        solved_extra_dependencies.append(key)

    return CallModel(
        call=call,
        serializer=serializer,
        params=tuple(
            i for i in class_fields if (
                i.field_name not in dependencies and
                i.field_name not in custom_fields
            )
        ),
        use_cache=use_cache,
        is_async=is_call_async,
        is_generator=is_call_generator,
        dependencies=dependencies,
        custom_fields=custom_fields,
        positional_args=positional_args,
        keyword_args=keyword_args,
        args_name=args_name,
        kwargs_name=kwargs_name,
        extra_dependencies=solved_extra_dependencies,
        dependency_provider=dependency_provider,
    )
