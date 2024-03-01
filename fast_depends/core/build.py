import inspect
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Type,
    Union,
)

from typing_extensions import (
    Annotated,
    ParamSpec,
    TypeVar,
    get_args,
    get_origin,
)

from fast_depends.core.model import CallModel
from fast_depends.dependencies import Depends
from fast_depends.library import CustomField
from fast_depends.library.caster import Caster, OptionItem
from fast_depends.utils import (
    get_typed_signature,
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
)

CUSTOM_ANNOTATIONS = (Depends, CustomField)


P = ParamSpec("P")
T = TypeVar("T")


def build_call_model(
    call: Union[
        Callable[P, T],
        Callable[P, Awaitable[T]],
    ],
    *,
    use_cache: bool = True,
    is_sync: Optional[bool] = None,
    extra_dependencies: Sequence[Depends] = (),
    caster_cls: Optional[Type[Caster]] = None,
    **caster_kwargs: Any,
) -> CallModel[P, T]:
    name = getattr(inspect.unwrap(call), "__name__", type(call).__name__)

    is_call_async = is_coroutine_callable(call)
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

    class_fields: List[OptionItem] = []
    dependencies: Dict[str, CallModel[..., Any]] = {}
    custom_fields: Dict[str, CustomField] = {}
    positional_args: List[str] = []
    keyword_args: List[str] = []
    args_name: Optional[str] = None
    kwargs_name: Optional[str] = None

    for param_name, param in typed_params.parameters.items():
        dep: Optional[Depends] = None
        custom: Optional[CustomField] = None

        if param.annotation is inspect.Parameter.empty:
            annotation = Any

        elif get_origin(param.annotation) is Annotated:
            annotated_args = get_args(param.annotation)
            type_annotation = annotated_args[0]
            custom_annotations = [
                arg for arg in annotated_args[1:] if isinstance(arg, CUSTOM_ANNOTATIONS)
            ]

            assert (
                len(custom_annotations) <= 1
            ), f"Cannot specify multiple `Annotated` Custom arguments for `{param_name}`!"

            next_custom = next(iter(custom_annotations), None)
            if next_custom is not None:
                if isinstance(next_custom, Depends):
                    dep = next_custom
                elif isinstance(next_custom, CustomField):
                    custom = next_custom
                else:  # pragma: no cover
                    raise AssertionError("unreachable")

                annotation = type_annotation
            else:
                annotation = param.annotation
        else:
            annotation = param.annotation

        default: Any
        if param_name == "args":
            default = ()
        elif param_name == "kwargs":
            default = {}
        else:
            default = param.default

        if isinstance(default, Depends):
            assert (
                not dep
            ), "You can not use `Depends` with `Annotated` and default both"
            dep = default

        elif isinstance(default, CustomField):
            assert (
                not custom
            ), "You can not use `CustomField` with `Annotated` and default both"
            custom = default

        else:
            class_fields.append(OptionItem(
                field_name=param_name,
                field_type=annotation,
                default_value=... if default is inspect.Parameter.empty else default
            ))

        if dep:
            dependencies[param_name] = build_call_model(
                dep.dependency,
                use_cache=dep.use_cache,
                is_sync=is_sync,
                caster_cls=caster_cls,
                **caster_kwargs,
            )

            if caster_cls is not None:
                class_fields.append(OptionItem(
                    field_name=param_name,
                    field_type=annotation,
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
                ))

            else:
                class_fields.append(OptionItem(
                    field_name=param_name,
                    field_type=Optional[annotation],
                    default_value=None,
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

    caster: Optional[Caster] = None
    if caster_cls is not None:
        caster = caster_cls(
            name=name,
            options=class_fields,
            response_type=return_annotation,
            **caster_kwargs,
        )

    return CallModel(
        call=call,
        caster=caster,
        params=tuple(i for i in class_fields if i.field_name not in dependencies and i.field_name not in custom_fields),
        use_cache=use_cache,
        is_async=is_call_async,
        is_generator=is_call_generator,
        dependencies=dependencies,
        custom_fields=custom_fields,
        positional_args=positional_args,
        keyword_args=keyword_args,
        args_name=args_name,
        kwargs_name=kwargs_name,
        extra_dependencies=[
            build_call_model(
                d.dependency,
                use_cache=d.use_cache,
                is_sync=is_sync,
                caster_cls=caster_cls,
                **caster_kwargs,
            )
            for d in extra_dependencies
        ],
    )
