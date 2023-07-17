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
    Union,
)

from typing_extensions import (
    Annotated,
    ParamSpec,
    TypeVar,
    assert_never,
    get_args,
    get_origin,
)

from fast_depends._compat import create_model
from fast_depends.core.model import CallModel
from fast_depends.dependencies import Depends
from fast_depends.library import CustomField
from fast_depends.utils import get_typed_signature, is_coroutine_callable

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

    class_fields: Dict[str, Tuple[Any, Any]] = {}
    dependencies: Dict[str, CallModel[..., Any]] = {}
    custom_fields: Dict[str, CustomField] = {}
    positional_args: List[str] = []
    keyword_args: List[str] = []
    for param in typed_params:
        dep: Optional[Depends] = None
        custom: Optional[CustomField] = None

        if param.annotation is inspect._empty:
            annotation = Any

        elif get_origin(param.annotation) is Annotated:
            annotated_args = get_args(param.annotation)
            type_annotation = annotated_args[0]
            custom_annotations = [
                arg for arg in annotated_args[1:] if isinstance(arg, CUSTOM_ANNOTATIONS)
            ]

            assert (
                len(custom_annotations) <= 1
            ), f"Cannot specify multiple `Annotated` Custom arguments for `{param.name}`!"

            next_custom = next(iter(custom_annotations), None)
            if next_custom is not None:
                if isinstance(next_custom, Depends):
                    dep = next_custom
                elif isinstance(next_custom, CustomField):
                    custom = next_custom
                else:  # pragma: no cover
                    assert_never()

                annotation = type_annotation
            else:
                annotation = param.annotation
        else:
            annotation = param.annotation

        if param.name == "args":
            default = ()
        elif param.name == "kwargs":
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

        elif default is inspect._empty:
            class_fields[param.name] = (annotation, ...)

        else:
            class_fields[param.name] = (annotation, default)

        if dep:
            dependencies[param.name] = build_call_model(
                dep.dependency,
                cast=dep.cast,
                use_cache=dep.use_cache,
                is_sync=is_sync,
            )

            if dep.cast is True:
                class_fields[param.name] = (annotation, ...)
            keyword_args.append(param.name)

        elif custom:
            assert not (
                is_sync and is_coroutine_callable(custom.use)
            ), f"You cannot use async custom field `{type(custom).__name__}` at sync `{name}`"

            custom.set_param_name(param.name)
            custom_fields[param.name] = custom

            if custom.cast is False:
                annotation = Any

            if custom.required:
                class_fields[param.name] = (annotation, ...)
            else:
                class_fields[param.name] = (Optional[annotation], None)
            keyword_args.append(param.name)

        else:
            if param.kind is param.KEYWORD_ONLY:
                keyword_args.append(param.name)
            elif param.name not in ("args", "kwargs"):
                positional_args.append(param.name)

    func_model = create_model(name, **class_fields)  # type: ignore

    if cast and return_annotation is not inspect._empty:
        response_model = create_model(
            "ResponseModel", response=(return_annotation, ...)
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
            )
            for d in extra_dependencies
        ],
    )
