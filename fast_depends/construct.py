import inspect
from typing import Any, ForwardRef, Optional, Tuple, Type, Union

from pydantic import BaseConfig
from pydantic.fields import (
    SHAPE_FROZENSET,
    SHAPE_LIST,
    SHAPE_SEQUENCE,
    SHAPE_SET,
    SHAPE_TUPLE,
    SHAPE_TUPLE_ELLIPSIS,
    FieldInfo,
    ModelField,
    Required,
    Undefined,
    UndefinedType,
)
from pydantic.schema import get_annotation_from_field_info
from pydantic.typing import evaluate_forwardref, get_args, get_origin
from typing_extensions import Annotated

from fast_depends import model
from fast_depends.library import CustomField
from fast_depends.types import AnyCallable, AnyDict
from fast_depends.utils import is_coroutine_callable

sequence_shapes = {
    SHAPE_LIST,
    SHAPE_SET,
    SHAPE_FROZENSET,
    SHAPE_TUPLE,
    SHAPE_SEQUENCE,
    SHAPE_TUPLE_ELLIPSIS,
}
sequence_types = (list, set, tuple)


def get_dependant(
    *,
    path: str,
    call: AnyCallable,
    name: Optional[str] = None,
    use_cache: bool = True,
) -> model.Dependant:
    dependant = model.Dependant(
        call=call,
        path=path,
        name=name,
        use_cache=use_cache,
        return_field=None,
    )

    is_async = is_coroutine_callable(call)

    endpoint_signature = get_typed_signature(call)
    signature_params = endpoint_signature.parameters

    for param in signature_params.values():
        custom, depends, param_field = analyze_param(
            param_name=param.name,
            annotation=param.annotation,
            default=param.default,
        )

        if param.name == model.RETURN_FIELD:
            dependant.return_field = param_field
            continue

        elif custom is not None:
            dependant.custom.append(custom)

        elif depends is not None:
            assert is_async or not is_coroutine_callable(
                depends.dependency
            ), f"You cannot use async dependency `{depends}` with sync `{dependant}`"

            sub_dependant = get_param_sub_dependant(
                param_name=param.name,
                depends=depends,
                path=path,
            )
            dependant.dependencies.append(sub_dependant)

        dependant.params.append(param_field)

    return dependant


def analyze_param(
    *,
    param_name: str,
    annotation: Any,
    default: Any,
) -> Tuple[Optional[CustomField], Optional[model.Depends], ModelField]:
    depends = None
    custom = None
    field_info = None

    if (
        annotation is not inspect.Signature.empty
        and get_origin(annotation) is Annotated  # type: ignore[comparison-overlap]
    ):
        annotated_args = get_args(annotation)
        custom_annotations = [
            arg
            for arg in annotated_args[1:]
            if isinstance(arg, (FieldInfo, model.Depends, CustomField))
        ]

        custom_annotations = next(iter(custom_annotations), None)
        if isinstance(custom_annotations, FieldInfo):
            field_info = custom_annotations
            assert field_info.default is Undefined or field_info.default is Required, (
                f"`{field_info.__class__.__name__}` default value cannot be set in"
                f" `Annotated` for {param_name!r}. Set the default value with `=` instead."
            )
            field_info.default = Required

        elif isinstance(custom_annotations, model.Depends):
            depends = custom_annotations

        elif isinstance(custom_annotations, CustomField):  # pragma: no branch
            custom_annotations.set_param_name(param_name)
            custom = custom_annotations
            if custom.cast is False:
                annotation = Any

    if isinstance(default, model.Depends):
        assert depends is None, (
            "Cannot specify `Depends` in `Annotated` and default value"
            f" together for {param_name!r}"
        )
        assert field_info is None, (
            "Cannot specify a annotation in `Annotated` and `Depends` as a"
            f" default value together for {param_name!r}"
        )
        depends = default

    elif isinstance(default, CustomField):
        default.set_param_name(param_name)
        custom = default
        if custom.cast is False:
            annotation = Any

    elif isinstance(default, FieldInfo):
        assert field_info is None, (
            "Cannot specify annotations in `Annotated` and default value"
            f" together for {param_name!r}"
        )
        field_info = default

    if (depends or custom) is not None:
        field = None

    if field_info is not None:
        annotation = get_annotation_from_field_info(
            annotation if annotation is not inspect.Signature.empty else Any,
            field_info,
            param_name,
        )
    else:
        field_info = FieldInfo(default=default)

    alias = field_info.alias or param_name

    if custom and custom.required is True:
        required = True
    else:
        required = field_info.default in (Required, Undefined, inspect._empty)

    field = create_response_field(
        name=param_name,
        type_=Any if depends and depends.cast is False else annotation,
        default=None if any((depends, custom)) else field_info.default,
        alias=alias,
        required=required,
        field_info=field_info,
    )

    return custom, depends, field


def get_typed_signature(call: AnyCallable) -> inspect.Signature:
    signature = inspect.signature(call)
    globalns = getattr(call, "__globals__", {})
    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=get_typed_annotation(param.annotation, globalns),
        )
        for param in signature.parameters.values()
    ]

    if signature.return_annotation is not signature.empty:
        typed_params.append(
            inspect.Parameter(
                name=model.RETURN_FIELD,
                kind=inspect._KEYWORD_ONLY,
                annotation=get_typed_annotation(signature.return_annotation, globalns),
            )
        )
    typed_signature = inspect.Signature(typed_params)
    return typed_signature


def get_typed_annotation(annotation: Any, globalns: AnyDict) -> Any:
    if isinstance(annotation, str):
        try:
            annotation = ForwardRef(annotation)
            annotation = evaluate_forwardref(annotation, globalns, globalns)
        except Exception:
            raise ValueError(  # noqa: B904
                f"Invalid filed annotation! Hint: check that {annotation} is a valid pydantic field type"
            )
    return annotation


def get_param_sub_dependant(
    *,
    param_name: str,
    depends: model.Depends,
    path: str,
) -> model.Dependant:
    assert depends.dependency
    return get_sub_dependant(
        depends=depends,
        dependency=depends.dependency,
        path=path,
        name=param_name,
    )


def get_sub_dependant(
    *,
    depends: model.Depends,
    dependency: AnyCallable,
    path: str,
    name: Optional[str] = None,
) -> model.Dependant:
    sub_dependant = get_dependant(
        path=path,
        call=dependency,
        name=name,
        use_cache=depends.use_cache,
    )
    return sub_dependant


def create_response_field(
    name: str,
    type_: Type[Any],
    default: Optional[Any] = None,
    required: Union[bool, UndefinedType] = True,
    field_info: Optional[FieldInfo] = None,
    alias: Optional[str] = None,
) -> ModelField:
    """
    Create a new response field. Raises if type_ is invalid.
    """
    try:
        return ModelField(
            name=name,
            type_=type_ if type_ is not inspect._empty else Any,
            default=default,
            required=required,
            class_validators={},
            model_config=BaseConfig,
            alias=alias,
            field_info=field_info or FieldInfo(),
        )
    except RuntimeError:  # pragma: no cover
        raise ValueError(  # noqa: B904
            f"Invalid args for response field! Hint: check that {type_} is a valid pydantic field type"
        )
