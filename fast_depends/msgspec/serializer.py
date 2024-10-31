import inspect
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import msgspec

from fast_depends.exceptions import ValidationError
from fast_depends.library.serializer import OptionItem, Serializer


class MsgSpecSerializer(Serializer):
    __slots__ = ("aliases", "model", "response_type", "name", "options", "response_option",)

    def __init__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ):
        model_options = []
        aliases = {}
        for i in options:
            if isinstance(msgspec.inspect.type_info(i.field_type), msgspec.inspect.CustomType):
                continue

            default_value = i.default_value

            if isinstance(default_value, msgspec._core.Field) and default_value.name:
                aliases[i.field_name] = default_value.name
            else:
                aliases[i.field_name] = i.field_name

            if default_value is Ellipsis:
                model_options.append((
                    i.field_name,
                    i.field_type,
                ))
            else:
                model_options.append((
                    i.field_name,
                    i.field_type,
                    default_value,
                ))

        self.aliases = aliases
        self.model = msgspec.defstruct(name, model_options, kw_only=True)

        if response_type is not inspect.Parameter.empty:
            self.response_type = response_type
        else:
            self.response_type = None

        super().__init__(name=name, options=options, response_type=response_type)

    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        with self._try_msgspec(call_kwargs, self.options):
            casted_model = msgspec.convert(
                call_kwargs,
                type=self.model,
                strict=False,
                str_keys=True,
            )

        return {
            out_field: getattr(casted_model, out_field, None)
            for out_field in self.aliases.keys()
        }

    def get_aliases(self) -> tuple[str, ...]:
        return tuple(self.aliases.values())

    def response(self, value: Any) -> Any:
        if self.response_type is not None:
            with self._try_msgspec(value, self.response_option, ("return",)):
                return msgspec.convert(value, type=self.response_type, strict=False)
        return value

    @property
    def json_schema(self) -> dict[str, Any]:
        return msgspec.json.schema(self.model)

    @contextmanager
    def _try_msgspec(self, call_kwargs: Any, options: dict[str, OptionItem], locations: Sequence[str] = (),) -> Iterator[None]:
        try:
            yield
        except msgspec.ValidationError as er:
            raise ValidationError(
                incoming_options=call_kwargs,
                expected=options,
                locations=locations or re.findall(r"at `\$\.(.)`", str(er.args)),
                original_error=er,
            ) from er
