import inspect
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, TypeVar

import msgspec

from fast_depends.exceptions import ValidationError
from fast_depends.library.schema import (
    SchemaField,
    apply_schema_groups,
    exclude_schema_fields,
    group_schema_fields,
)
from fast_depends.library.schema_processing import SchemaExclude, process_schema
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
        response_type: Any = inspect.Parameter.empty,
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

    def get_schema(
        self,
        *,
        embed: bool = False,
        exclude: Iterable[SchemaExclude] = (),
        resolve_refs: bool = False,
    ) -> dict[str, Any]:
        return process_schema(
            self._get_schema(tuple(exclude)), embed=embed, resolve_refs=resolve_refs
        )

    def _get_schema(self, exclude: tuple[SchemaExclude, ...]) -> dict[str, Any]:
        if self._schema_options is None and not exclude:
            schema: dict[str, Any] = msgspec.json.schema(self.model)
            return schema

        options = exclude_schema_fields(
            self._schema_options()
            if self._schema_options
            else list(self.options.values()),
            exclude,
        )
        if not any(isinstance(i, SchemaField) for i in options):
            schema = msgspec.json.schema(self._schema_model(self.name, options))
            return schema

        groups = group_schema_fields(options)
        root_options = list(groups[None])
        aliases: dict[str | None, dict[str, str]] = {}
        for index, (source, fields) in enumerate(groups.items()):
            if source is None:
                continue
            model = self._schema_model(f"{self.name}__source_{index}", fields)
            aliases[source] = {
                f.name: f.encode_name for f in msgspec.structs.fields(model)
            }
            field_name = f"source_{index}"
            while field_name in {i.field_name for i in root_options}:
                field_name += "_"
            root_options.append(
                OptionItem(field_name, model, default_value=msgspec.field(name=source))
            )

        model = self._schema_model(self.name, root_options)
        root_aliases = {f.name: f.encode_name for f in msgspec.structs.fields(model)}
        aliases[None] = {i.field_name: root_aliases[i.field_name] for i in groups[None]}
        return apply_schema_groups(msgspec.json.schema(model), groups, aliases)

    @staticmethod
    def _schema_model(name: str, options: list[OptionItem]) -> type[msgspec.Struct]:
        return msgspec.defstruct(
            name,
            [
                (i.field_name, i.field_type)
                if i.default_value is Ellipsis
                else (i.field_name, i.field_type, i.default_value)
                for i in options
            ],
            kw_only=True,
        )

    def get_response_schema(self) -> dict[str, Any] | None:
        response_type = self.response_option["return"].field_type
        if response_type is inspect.Parameter.empty:
            return None
        schema: dict[str, Any] = msgspec.json.schema(response_type)
        return schema

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
