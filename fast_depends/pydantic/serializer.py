import inspect
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from functools import partial
from itertools import chain
from typing import Any

from pydantic import Field
from pydantic import ValidationError as PValidationError

from fast_depends.exceptions import ValidationError
from fast_depends.library.schema import (
    SchemaField,
    apply_schema_groups,
    exclude_schema_fields,
    group_schema_fields,
    unique_schema_names,
)
from fast_depends.library.schema_processing import SchemaExclude, process_schema
from fast_depends.library.serializer import (
    InputField,
    OptionItem,
    PreparedInputs,
    Serializer,
    SerializerProto,
)
from fast_depends.pydantic._compat import (
    BaseModel,
    ConfigDict,
    TypeAdapter,
    create_model,
    dump_json,
    get_aliases,
    get_config_base,
    get_json_encoder,
    get_model_fields,
    get_schema_aliases,
    model_schema,
    response_adapter,
    type_schema,
)
from fast_depends.pydantic.preparation import PydanticPreparation


def _encode(message: Any, *, encoder: Callable[[Any], bytes] = dump_json) -> bytes:
    if isinstance(message, bytes):
        return message
    return encoder(message)


class PydanticSerializer(SerializerProto):
    __slots__ = (
        "config",
        "use_fastdepends_errors",
    )

    # Keep class-level calls as the default encoder; instances bind their config.
    encode: Callable[[Any], bytes] = staticmethod(_encode)

    def __init__(
        self,
        pydantic_config: ConfigDict | None = None,
        use_fastdepends_errors: bool = True,
    ) -> None:
        self.config = pydantic_config
        self.use_fastdepends_errors = use_fastdepends_errors
        if type(self).encode is PydanticSerializer.encode:
            self.encode = partial(_encode, encoder=get_json_encoder(pydantic_config))

    def __call__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ) -> "_PydanticSerializer":
        serializer_type: type[_PydanticSerializer]
        if self.use_fastdepends_errors:
            serializer_type = (
                _PydanticWrappedSerializerWithResponse
                if response_type is not inspect.Parameter.empty
                else _PydanticWrappedSerializer
            )
        else:
            serializer_type = (
                _PydanticSerializerWithResponse
                if response_type is not inspect.Parameter.empty
                else _PydanticSerializer
            )
        serializer = serializer_type(
            name=name,
            options=options,
            response_type=response_type,
            pydantic_config=self.config,
        )
        serializer._response_encoder = self.encode
        return serializer


class _PydanticSerializer(Serializer):
    __slots__ = (
        "model",
        "name",
        "options",
        "config",
        "response_option",
        "_response_encoder",
        "_preparation",
    )

    _response_encoder: Callable[[Any], bytes]

    def __init__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any = inspect.Parameter.empty,
        pydantic_config: ConfigDict | None = None,
    ):
        class_options: dict[str, Any] = {
            i.field_name: (i.field_type, i.default_value) for i in options
        }

        self.config = get_config_base(pydantic_config)
        self._preparation: PydanticPreparation | None = None

        self.model = create_model(  # type: ignore[call-overload]
            name,
            __config__=self.config,
            **class_options,
        )

        super().__init__(name=name, options=options, response_type=response_type)

    def get_aliases(self) -> tuple[str, ...]:
        return get_aliases(self.model)

    def _prepare(self) -> PydanticPreparation:
        if self._preparation is None:
            self._preparation = PydanticPreparation(
                self.model,
                self.options,
                wrap_errors=hasattr(self, "_try_pydantic"),
            )
        return self._preparation

    def prepare_fields(self) -> dict[str, InputField]:
        return self._prepare().fields

    def prepare_inputs(self, fields: Sequence[InputField]) -> PreparedInputs:
        return self._prepare().prepare_inputs(fields)

    def validate_resolved(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._prepare().validate_resolved(values)

    def _prepare_call(
        self, *, staged: bool
    ) -> Callable[[dict[str, Any]], dict[str, Any]]:
        if staged:
            prepared = self._prepare()
            prepared.prepare_resolved()
            return prepared.validate_resolved
        return self

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
            return model_schema(self.model)

        options = exclude_schema_fields(
            self._schema_options()
            if self._schema_options
            else list(self.options.values()),
            exclude,
        )
        options = unique_schema_names(options, self._schema_field)
        if not any(isinstance(i, SchemaField) for i in options):
            return model_schema(self._schema_model(self.name, options))

        groups = group_schema_fields(options)
        root_options = list(groups[None])
        aliases: dict[str | None, dict[str, str]] = {}
        for index, (source, fields) in enumerate(groups.items()):
            if source is None:
                continue
            model = self._schema_model(f"{self.name}__source_{index}", fields)
            aliases[source] = get_schema_aliases(model)
            field_name = f"source_{index}"
            while field_name in {i.field_name for i in root_options}:
                field_name += "_"
            root_options.append(
                OptionItem(field_name, model, default_value=Field(..., alias=source))
            )

        model = self._schema_model(self.name, root_options)
        root_aliases = get_schema_aliases(model)
        aliases[None] = {
            i.field_name: root_aliases[i.field_name]
            for i in groups[None]
            if i.field_name in root_aliases
        }
        return apply_schema_groups(model_schema(model), groups, aliases)

    def _schema_model(self, name: str, options: list[OptionItem]) -> type[BaseModel]:
        return create_model(  # type: ignore[call-overload, no-any-return]
            name,
            __config__=self.config,
            **{i.field_name: (i.field_type, i.default_value) for i in options},
        )

    def _schema_field(self, option: OptionItem) -> tuple[Any, Any, str]:
        model = self._schema_model(self.name, [option])
        field = model.model_fields[option.field_name]
        attributes = field.asdict()["attributes"]
        for alias in ("alias", "validation_alias", "serialization_alias"):
            if attributes[alias] is None:
                attributes[alias] = option.field_name
        attributes["alias_priority"] = 2
        default = Field(**attributes)
        default.metadata = field.metadata.copy()
        return (
            field.annotation,
            default,
            get_schema_aliases(model).get(option.field_name, option.field_name),
        )

    def encode(self, value: Any) -> bytes:
        return self._response_encoder(value)

    def get_response_schema(self) -> dict[str, Any] | None:
        return None

    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        casted_model = self.model(**call_kwargs)

        return {
            i: getattr(casted_model, i) for i in get_model_fields(casted_model).keys()
        }


class _PydanticSerializerWithResponse(_PydanticSerializer):
    __slots__ = ("response_adapter", "response_config", "response_callback")

    response_adapter: TypeAdapter[Any]

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

        self.response_adapter, self.response_config = response_adapter(
            response_type, self.config
        )
        self.response_callback = (
            response_type.model_validate
            if isinstance(response_type, type) and issubclass(response_type, BaseModel)
            else self.response_adapter.validate_python
        )

    def response(self, value: Any) -> Any:
        return self.response_callback(value)

    def encode(self, value: Any) -> bytes:
        return self.response_adapter.dump_json(value, by_alias=True)

    def get_response_schema(self) -> dict[str, Any]:
        return type_schema(self.response_adapter, self.response_config)


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
            return super().response(value)
