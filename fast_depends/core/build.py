import inspect
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
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

from fast_depends._compat import ConfigDict, create_model, get_config_base
from fast_depends.core.model import CallModel, ResponseModel
from fast_depends.dependencies import Depends
from fast_depends.library import CustomField
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
    cast: bool = True,
    use_cache: bool = True,
    is_sync: Optional[bool] = None,
    extra_dependencies: Sequence[Depends] = (),
    pydantic_config: Optional[ConfigDict] = None,
) -> CallModel[P, T]:
    name = getattr(call, "__name__", type(call).__name__)

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

    class_fields: Dict[str, Tuple[Any, Any]] = {}
    dependencies: Dict[str, "CallModel[..., Any]"] = {}
    custom_fields: Dict[str, CustomField] = {}
    positional_args: List[str] = []
    keyword_args: List[str] = []

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

        elif default is inspect.Parameter.empty:
            class_fields[param_name] = (annotation, ...)

        else:
            class_fields[param_name] = (annotation, default)

        if dep:
            if not cast:
                dep.cast = False

            dependencies[param_name] = build_call_model(
                dep.dependency,
                cast=dep.cast,
                use_cache=dep.use_cache,
                is_sync=is_sync,
                pydantic_config=pydantic_config,
            )

            if dep.cast is True:
                class_fields[param_name] = (annotation, ...)
            keyword_args.append(param_name)

        elif custom:
            assert not (
                is_sync and is_coroutine_callable(custom.use)
            ), f"You cannot use async custom field `{type(custom).__name__}` at sync `{name}`"

            custom.set_param_name(param_name)
            custom_fields[param_name] = custom

            if custom.cast is False:
                annotation = Any

            if custom.required:
                class_fields[param_name] = (annotation, ...)
            else:
                class_fields[param_name] = (Optional[annotation], None)
            keyword_args.append(param_name)

        else:
            if param.kind is param.KEYWORD_ONLY:
                keyword_args.append(param_name)
            elif param_name not in ("args", "kwargs"):
                positional_args.append(param_name)

    func_model = create_model(  # type: ignore[call-overload]
        name,
        __config__=get_config_base(pydantic_config),
        **class_fields,
    )

    response_model: Optional[Type[ResponseModel[T]]]
    if cast and return_annotation and return_annotation is not inspect.Parameter.empty:
        response_model = create_model(  # type: ignore[assignment]
            "ResponseModel",
            __config__=get_config_base(pydantic_config),
            response=(return_annotation, ...),
        )
    else:
        response_model = None

    return CallModel(
        call=call,
        model=func_model,
        response_model=response_model,
        cast=cast,
        use_cache=use_cache,
        is_async=is_call_async,
        is_generator=is_call_generator,
        dependencies=dependencies,
        custom_fields=custom_fields,
        positional_args=positional_args,
        keyword_args=keyword_args,
        extra_dependencies=[
            build_call_model(
                d.dependency,
                cast=d.cast,
                use_cache=d.use_cache,
                is_sync=is_sync,
                pydantic_config=pydantic_config,
            )
            for d in extra_dependencies
        ],
    )
