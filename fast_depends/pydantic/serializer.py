import inspect
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from itertools import chain
from typing import Any

from pydantic import ValidationError as PValidationError

from fast_depends.exceptions import ValidationError
from fast_depends.library.serializer import OptionItem, Serializer, SerializerProto
from fast_depends.pydantic._compat import (
    PYDANTIC_V2,
    BaseModel,
    ConfigDict,
    PydanticUserError,
    TypeAdapter,
    create_model,
    dump_json,
    get_aliases,
    get_config_base,
    get_model_fields,
)


class PydanticSerializer(SerializerProto):
    __slots__ = (
        "config",
        "use_fastdepends_errors",
    )

    def __init__(
        self,
        pydantic_config: ConfigDict | None = None,
        use_fastdepends_errors: bool = True,
    ) -> None:
        self.config = pydantic_config
        self.use_fastdepends_errors = use_fastdepends_errors

    def __call__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ) -> "_PydanticSerializer":
        if self.use_fastdepends_errors:
            if response_type is not inspect.Parameter.empty:
                return _PydanticWrappedSerializerWithResponse(
                    name=name,
                    options=options,
                    response_type=response_type,
                    pydantic_config=self.config,
                )

            return _PydanticWrappedSerializer(
                name=name,
                options=options,
                pydantic_config=self.config,
            )

        if response_type is not inspect.Parameter.empty:
            return _PydanticSerializerWithResponse(
                name=name,
                options=options,
                response_type=response_type,
                pydantic_config=self.config,
            )

        return _PydanticSerializer(
            name=name,
            options=options,
            pydantic_config=self.config,
        )

    @staticmethod
    def encode(message: Any) -> bytes:
        if isinstance(message, bytes):
            return message
        return dump_json(message)


class _PydanticSerializer(Serializer):
    __slots__ = (
        "model",
        "name",
        "options",
        "config",
        "response_option",
    )

    def __init__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any = None,
        pydantic_config: ConfigDict | None = None,
    ):
        class_options: dict[str, Any] = {
            i.field_name: (i.field_type, i.default_value) for i in options
        }

        self.config = get_config_base(pydantic_config)

        self.model = create_model(  # type: ignore[call-overload]
            name,
            __config__=self.config,
            **class_options,
        )

        super().__init__(name=name, options=options, response_type=response_type)

    def get_aliases(self) -> tuple[str, ...]:
        return get_aliases(self.model)

    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        casted_model = self.model(**call_kwargs)

        return {
            i: getattr(casted_model, i) for i in get_model_fields(casted_model).keys()
        }


class _PydanticSerializerWithResponse(_PydanticSerializer):
    __slots__ = ("response_callback",)

    response_callback: Callable[[Any], Any]

    def __init__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
        pydantic_config: ConfigDict | None = None,
    ):
        super().__init__(
            name=name,
            options=options,
            response_type=response_type,
            pydantic_config=pydantic_config,
        )

        response_callback: Callable[[Any], Any] | None = None
        try:
            is_model = issubclass(response_type or object, BaseModel)
        except Exception:
            is_model = False

        if is_model:
            if PYDANTIC_V2:
                response_callback = response_type.model_validate
            else:
                response_callback = response_type.validate

        elif PYDANTIC_V2:
            try:
                response_pydantic_type = TypeAdapter(response_type, config=self.config)
            except PydanticUserError:
                response_pydantic_type = TypeAdapter(response_type)
            response_callback = response_pydantic_type.validate_python

        if response_callback is None and not PYDANTIC_V2:
            response_model = create_model(  # type: ignore[call-overload]
                "ResponseModel",
                __config__=self.config,
                r=(response_type or Any, ...),
            )

            def response_callback(x: Any) -> Any:
                return response_model(r=x).r  # type: ignore[attr-defined]

        assert response_callback
        self.response_callback = response_callback

    def response(self, value: Any) -> Any:
        return self.response_callback(value)


class _PydanticWrappedSerializer(_PydanticSerializer):
    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        with self._try_pydantic(call_kwargs, self.options):
            casted_model = self.model(**call_kwargs)

        return {
            i: getattr(casted_model, i) for i in get_model_fields(casted_model).keys()
        }

    @contextmanager
    def _try_pydantic(
        self,
        call_kwargs: Any,
        options: dict[str, OptionItem],
        locations: Sequence[Any] = (),
    ) -> Iterator[None]:
        try:
            yield
        except PValidationError as er:
            raise ValidationError(
                incoming_options=call_kwargs,
                expected=options,
                locations=locations
                or tuple(chain(*(one_error["loc"] for one_error in er.errors()))),
                original_error=er,
            ) from er


class _PydanticWrappedSerializerWithResponse(
    _PydanticWrappedSerializer,
    _PydanticSerializerWithResponse,
):
    def response(self, value: Any) -> Any:
        with self._try_pydantic(value, self.response_option, ("return",)):
            return self.response_callback(value)
