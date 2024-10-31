import inspect
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from itertools import chain
from typing import Any, Callable, Optional

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
    get_aliases,
    get_config_base,
    get_model_fields,
)


class PydanticSerializer(SerializerProto):
    __slots__ = ("pydantic_config",)

    def __init__(self, pydantic_config: Optional[ConfigDict] = None) -> None:
        self.config = pydantic_config

    def __call__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ) -> "_PydanticSerializer":
        return _PydanticSerializer(
            name=name,
            options=options,
            response_type=response_type,
            pydantic_config=self.config,
        )


class _PydanticSerializer(Serializer):
    __slots__ = ("model", "response_callback", "name", "options", "response_option",)

    def __init__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
        pydantic_config: Optional[ConfigDict] = None,
    ):
        class_options: dict[str, Any] = {
            i.field_name: (i.field_type, i.default_value)
            for i in options
        }

        config = get_config_base(pydantic_config)

        self.model = create_model(
            name,
            __config__=config,
            **class_options,
        )

        self.response_callback: Optional[Callable[[Any], Any]] = None

        if response_type is not inspect.Parameter.empty:
            try:
                is_model = issubclass(response_type or object, BaseModel)
            except Exception:
                is_model = False

            if is_model:
                if PYDANTIC_V2:
                    self.response_callback = response_type.model_validate
                else:
                    self.response_callback = response_type.validate

            elif PYDANTIC_V2:
                try:
                    response_pydantic_type = TypeAdapter(response_type, config=config)
                except PydanticUserError:
                    pass
                else:
                    self.response_callback = response_pydantic_type.validate_python

            if self.response_callback is None and not (response_type is None and not PYDANTIC_V2):
                response_model = create_model(
                    "ResponseModel",
                    __config__=config,
                    r=(response_type or Any, ...),
                )

                self.response_callback = lambda x: response_model(r=x).r  # type: ignore[attr-defined]

        super().__init__(name=name, options=options, response_type=response_type)

    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        with self._try_pydantic(call_kwargs, self.options):
            casted_model = self.model(**call_kwargs)

        return {
            i: getattr(casted_model, i)
            for i in get_model_fields(casted_model).keys()
        }

    def get_aliases(self) -> tuple[str, ...]:
        return get_aliases(self.model)

    def response(self, value: Any) -> Any:
        if self.response_callback is not None:
            with self._try_pydantic(value, self.response_option, ("return",)):
                return self.response_callback(value)
        return value

    @contextmanager
    def _try_pydantic(self, call_kwargs: Any, options: dict[str, OptionItem], locations: Sequence[str] = (),) -> Iterator[None]:
        try:
            yield
        except PValidationError as er:
            raise ValidationError(
                incoming_options=call_kwargs,
                expected=options,
                locations=locations or tuple(chain(*(one_error["loc"] for one_error in er.errors()))),
                original_error=er,
            ) from er
