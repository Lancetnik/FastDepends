from collections.abc import Hashable, Sequence
from itertools import chain
from typing import Any

from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo
from pydantic_core import SchemaValidator, core_schema
from pydantic_core import ValidationError as PydanticValidationError

from fast_depends.exceptions import ValidationError
from fast_depends.library.serializer import InputField, OptionItem, PreparedValue

_MISSING = object()


def _unwrap(value: PreparedValue) -> Any:
    return value.value


def _prepared_tag(value: Any) -> str:
    return "prepared" if isinstance(value, PreparedValue) else "raw"


def _schema_option(option: OptionItem) -> OptionItem:
    default = option.default_value
    if isinstance(default, FieldInfo):
        attributes = default.asdict()["attributes"]
        default = Field(
            **{
                key: value
                for key, value in attributes.items()
                if key not in ("default", "default_factory")
            }
        )
        default.metadata = option.default_value.metadata.copy()
    else:
        default = Ellipsis
    return OptionItem(
        option.field_name,
        option.field_type,
        source=option.source,
        default_value=default,
        kind=option.kind,
    )


def _validation_contract(value: Any) -> Any:
    if isinstance(value, dict):
        excluded = (
            {"metadata", "serialization"} if isinstance(value.get("type"), str) else set()
        )
        return {
            key: _validation_contract(item)
            for key, item in value.items()
            if key not in excluded
        }
    if isinstance(value, list):
        return [_validation_contract(item) for item in value]
    return value


def _has_context(
    schema: Any, definitions: dict[str, Any], visited: frozenset[str] = frozenset()
) -> bool:
    if isinstance(schema, dict):
        if schema.get("type") == "model-fields":
            # Validators below this boundary receive model-local field data.
            return False
        if schema.get("type") == "definition-ref":
            reference = schema["schema_ref"]
            return reference not in visited and _has_context(
                definitions[reference], definitions, visited | {reference}
            )
        function = schema.get("function")
        if isinstance(function, dict) and function.get("type") == "with-info":
            return True
        return any(
            _has_context(item, definitions, visited)
            for key, item in schema.items()
            if not isinstance(schema.get("type"), str)
            or key not in ("metadata", "serialization", "default", "default_factory")
        )
    if isinstance(schema, (tuple, list)):
        return any(_has_context(item, definitions, visited) for item in schema)
    return False


def _split(schema: Any, definitions: dict[str, Any]) -> tuple[Any, Any]:
    kind = schema["type"]
    if kind == "function-plain" and schema["function"]["type"] == "with-info":
        return core_schema.any_schema(), schema
    if kind in ("function-before", "function-after", "function-wrap"):
        contextual = schema["function"]["type"] == "with-info"
        if contextual and kind != "function-after":
            return core_schema.any_schema(), schema
        before, after = _split(schema["schema"], definitions)
        if kind == "function-after":
            if contextual or after["type"] != "any":
                return before, {**schema, "schema": after}
            return {**schema, "schema": before}, after
        if kind == "function-before":
            return {**schema, "schema": before}, after
        if after["type"] == "any":
            return {**schema, "schema": before}, after
        return core_schema.any_schema(), schema
    if _has_context(schema, definitions):
        raise TypeError("Cannot split a contextual validator inside this input type")
    return schema, core_schema.any_schema()


def _paths(
    field: dict[str, Any], name: str, config: dict[str, Any]
) -> tuple[tuple[str | int, ...], ...]:
    alias = field.get("validation_alias")
    if alias is None or config.get("validate_by_alias") is False:
        return ((name,),)
    paths: tuple[tuple[str | int, ...], ...]
    if isinstance(alias, str):
        paths = ((alias,),)
    elif alias and isinstance(alias[0], list):
        paths = tuple(tuple(path) for path in alias)
    else:
        paths = (tuple(alias),)
    if config.get("validate_by_name") and (name,) not in paths:
        paths += ((name,),)
    return paths


class _FieldSchema:
    __slots__ = ("field", "input", "definitions")

    def __init__(self, field: Any, before: Any, definitions: list[Any]) -> None:
        self.field = field
        self.input = before
        self.definitions = definitions


class _PreparedInputs:
    __slots__ = ("validator", "keys", "options", "wrap_errors", "empty")

    def __init__(
        self, fields: Sequence[InputField], config: Any, wrap_errors: bool
    ) -> None:
        native: dict[str, Any] = {}
        self.keys: dict[str, Hashable] = {}
        self.options = {field.option.field_name: field.option for field in fields}
        self.wrap_errors = wrap_errors
        configuration = {
            key: value
            for key, value in config.items()
            if key != "title" and not key.startswith("ser_json_")
        }
        self.empty = not fields and config.get("extra_fields_behavior") != "forbid"
        definitions: dict[str, Any] = {}
        for index, field in enumerate(fields):
            if (
                not isinstance(field.schema, _FieldSchema)
                or field.contract[1] != configuration
            ):
                raise TypeError(
                    "A shared input graph cannot mix Pydantic validation configurations"
                )
            name = f"input_{index}"
            prepared: _FieldSchema = field.schema
            schema: Any = core_schema.no_info_after_validator_function(
                PreparedValue, prepared.input
            )
            if not field.required:
                schema = core_schema.with_default_schema(
                    schema, default=_MISSING, validate_default=False
                )
            native[name] = {
                **prepared.field,
                "schema": schema,
                "validation_alias": [list(path) for path in field.paths],
            }
            self.keys[name] = field.key
            definitions.update({item["ref"]: item for item in prepared.definitions})
        inputs: Any = core_schema.model_fields_schema(native)
        if definitions:
            inputs = core_schema.definitions_schema(inputs, list(definitions.values()))
        self.validator = SchemaValidator(inputs, config)

    def __call__(self, values: dict[str, Any]) -> dict[Hashable, PreparedValue]:
        if self.empty:
            return {}
        try:
            prepared, _, supplied = self.validator.validate_python(
                values, by_alias=True, by_name=False
            )
        except PydanticValidationError as error:
            if not self.wrap_errors:
                raise
            _raise_validation_error(error, values, self.options)
        return {self.keys[name]: prepared[name] for name in supplied if name in self.keys}


def _raise_validation_error(
    error: PydanticValidationError, values: dict[str, Any], options: dict[str, OptionItem]
) -> Any:
    raise ValidationError(
        incoming_options={
            name: value.value if isinstance(value, PreparedValue) else value
            for name, value in values.items()
        },
        expected=options,
        locations=tuple(chain.from_iterable(item["loc"] for item in error.errors())),
        original_error=error,
    ) from error


class PydanticPreparation:
    __slots__ = (
        "fields",
        "validator",
        "config",
        "options",
        "wrap_errors",
        "fast_fields",
        "resolved_schema",
    )

    def __init__(
        self,
        model: type[BaseModel],
        options: dict[str, OptionItem],
        *,
        wrap_errors: bool,
    ) -> None:
        root = model.__pydantic_core_schema__
        definitions = []
        if root["type"] == "definitions":
            definitions = root["definitions"]
            root = root["schema"]
        if root["type"] != "model" or root["schema"]["type"] != "model-fields":
            raise TypeError("Staged validation requires a generated argument model")
        self.config = root.get("config", {})
        self.options = options
        self.wrap_errors = wrap_errors
        self.fields: dict[str, InputField] = {}
        complete = True
        native = dict(root["schema"]["fields"])
        references = {item["ref"]: item for item in definitions}
        for name, option in options.items():
            if option.source is not None:
                continue
            field = native[name]
            schema = field["schema"]
            default = schema if schema["type"] == "default" else None
            full = default["schema"] if default is not None else schema
            try:
                before, after = _split(full, references)
            except TypeError as error:
                raise TypeError(
                    f"Cannot prepare input {model.__name__}.{name}: {error}"
                ) from error
            complete = complete and after["type"] == "any"
            paths = _paths(field, name, self.config)
            self.fields[name] = InputField(
                option,
                key=(option.source, paths[0]),
                paths=paths,
                required=default is None,
                contract=(
                    _validation_contract(full),
                    {
                        key: value
                        for key, value in self.config.items()
                        if key != "title" and not key.startswith("ser_json_")
                    },
                    _paths(field, name, {**self.config, "validate_by_name": False}),
                ),
                schema=_FieldSchema(field, before, definitions),
                schema_option=_schema_option(option),
            )
            prepared = core_schema.no_info_before_validator_function(_unwrap, after)
            selected: Any = core_schema.tagged_union_schema(
                {"prepared": prepared, "raw": full}, _prepared_tag
            )
            if default is not None:
                selected = {**default, "schema": selected}
            native[name] = {**field, "schema": selected}
        resolved: Any = {**root["schema"], "fields": native}
        if definitions:
            resolved = core_schema.definitions_schema(resolved, definitions)
        self.resolved_schema = resolved
        self.validator: SchemaValidator | None = None
        self.fast_fields = (
            tuple(options) if complete and len(self.fields) == len(options) else None
        )

    def prepare_inputs(self, fields: Sequence[InputField]) -> _PreparedInputs:
        return _PreparedInputs(fields, self.config, self.wrap_errors)

    def prepare_resolved(self) -> SchemaValidator:
        if self.validator is None:
            self.validator = SchemaValidator(self.resolved_schema, self.config)
        return self.validator

    def validate_resolved(self, values: dict[str, Any]) -> dict[str, Any]:
        names = self.fast_fields
        if names is not None and len(values) == len(names):
            if all(isinstance(values.get(name), PreparedValue) for name in names):
                return {name: values[name].value for name in names}
        result: dict[str, Any]
        try:
            result, _, _ = self.prepare_resolved().validate_python(
                values, by_alias=False, by_name=True
            )
        except PydanticValidationError as error:
            if not self.wrap_errors:
                raise
            _raise_validation_error(error, values, self.options)
        return result
