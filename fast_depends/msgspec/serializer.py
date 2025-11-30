import inspect
import re
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, TypeVar

import msgspec

from fast_depends.exceptions import ValidationError
from fast_depends.library.serializer import OptionItem, Serializer, SerializerProto

T = TypeVar("T")


class MsgSpecSerializer(SerializerProto):
    __slots__ = ("use_fastdepends_errors", "dec_hook")

    def __init__(
        self,
        use_fastdepends_errors: bool = True,
        dec_hook: Callable[[type[T], Any], T] | None = None,
    ) -> None:
        self.use_fastdepends_errors = use_fastdepends_errors
        self.dec_hook = dec_hook

    def __call__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ) -> "_MsgSpecSerializer":
        if self.use_fastdepends_errors:
            if response_type is not inspect.Parameter.empty:
                return _MsgSpecWrappedSerializerWithResponse(
                    name=name,
                    options=options,
                    response_type=response_type,
                    dec_hook=self.dec_hook,
                )

            return _MsgSpecWrappedSerializer(
                name=name,
                options=options,
                dec_hook=self.dec_hook,
            )

        if response_type is not inspect.Parameter.empty:
            return _MsgSpecSerializerWithResponse(
                name=name,
                options=options,
                response_type=response_type,
                dec_hook=self.dec_hook,
            )

        return _MsgSpecSerializer(
            name=name,
            options=options,
            dec_hook=self.dec_hook,
        )

    @staticmethod
    def encode(message: Any) -> bytes:
        if isinstance(message, bytes):
            return message
        return msgspec.json.encode(message)


class _MsgSpecSerializer(Serializer):
    __slots__ = (
        "aliases",
        "model",
        "response_type",
        "name",
        "options",
        "response_option",
        "dec_hook",
    )

    def __init__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any = None,
        dec_hook: Callable[[type[T], Any], T] | None = None,
    ):
        model_options: list[str | tuple[str, type] | tuple[str, type, Any]] = []
        aliases = {}
        for i in options:
            default_value = i.default_value

            if isinstance(default_value, msgspec._core.Field) and default_value.name:
                aliases[i.field_name] = default_value.name
            else:
                aliases[i.field_name] = i.field_name

            if default_value is Ellipsis:
                model_options.append(
                    (
                        i.field_name,
                        i.field_type,
                    )
                )
            else:
                model_options.append(
                    (
                        i.field_name,
                        i.field_type,
                        default_value,
                    )
                )

        self.aliases = aliases
        self.model = msgspec.defstruct(name, model_options, kw_only=True)
        self.dec_hook = dec_hook
        super().__init__(name=name, options=options, response_type=response_type)

    def get_aliases(self) -> tuple[str, ...]:
        return tuple(self.aliases.values())

    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        casted_model = msgspec.convert(
            call_kwargs,
            type=self.model,
            strict=False,
            str_keys=True,
            dec_hook=self.dec_hook,
        )

        return {
            out_field: getattr(casted_model, out_field, None)
            for out_field in self.aliases.keys()
        }


class _MsgSpecSerializerWithResponse(_MsgSpecSerializer):
    def __init__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
        dec_hook: Callable[[type[T], Any], T] | None = None,
    ):
        super().__init__(
            name=name,
            options=options,
            response_type=response_type,
            dec_hook=dec_hook,
        )
        self.response_type = response_type

    def response(self, value: Any) -> Any:
        return msgspec.convert(
            value,
            type=self.response_type,
            strict=False,
            dec_hook=self.dec_hook,
        )


class _MsgSpecWrappedSerializer(_MsgSpecSerializer):
    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        with self._try_msgspec(call_kwargs, self.options):
            casted_model = msgspec.convert(
                call_kwargs,
                type=self.model,
                strict=False,
                str_keys=True,
                dec_hook=self.dec_hook,
            )

        return {
            out_field: getattr(casted_model, out_field, None)
            for out_field in self.aliases.keys()
        }

    @contextmanager
    def _try_msgspec(
        self,
        call_kwargs: Any,
        options: dict[str, OptionItem],
        locations: Sequence[str] = (),
    ) -> Iterator[None]:
        try:
            yield
        except msgspec.ValidationError as er:
            raise ValidationError(
                incoming_options=call_kwargs,
                expected=options,
                locations=locations or re.findall(r"at `\$\.(.)`", str(er.args)),
                original_error=er,
            ) from er


class _MsgSpecWrappedSerializerWithResponse(_MsgSpecWrappedSerializer):
    def __init__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
        dec_hook: Callable[[type[T], Any], T] | None = None,
    ):
        super().__init__(
            name=name,
            options=options,
            response_type=response_type,
            dec_hook=dec_hook,
        )
        self.response_type = response_type

    def response(self, value: Any) -> Any:
        with self._try_msgspec(value, self.response_option, ("return",)):
            return msgspec.convert(
                value,
                type=self.response_type,
                strict=False,
                dec_hook=self.dec_hook,
            )
