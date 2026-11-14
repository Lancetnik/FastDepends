from collections.abc import Callable
from functools import partial
from typing import Any, cast

from pydantic import AliasChoices, BaseModel, ConfigDict, TypeAdapter, create_model
from pydantic._internal._config import ConfigWrapper
from pydantic.errors import PydanticUserError
from pydantic.fields import FieldInfo
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import CoreConfig, SchemaSerializer, to_json
from pydantic_core.core_schema import any_schema

__all__ = (
    "BaseModel",
    "create_model",
    "get_config_base",
    "ConfigDict",
    "TypeAdapter",
    "PydanticUserError",
    "dump_json",
    "get_json_encoder",
)

default_pydantic_config = {"arbitrary_types_allowed": True}


class _ResponseSchema(GenerateJsonSchema):
    """TypeAdapter serialization schemas with configuration compatibility."""

    def __init__(self, config: ConfigDict) -> None:
        super().__init__()
        self._json_configs = [config]
        self._definitions: dict[str, Any] = {}
        self._contexts: dict[str, int] = {}
        self._scoped_definitions: dict[str, Any] = {}
        self._generating: set[str] = set()

    @property
    def _config(self) -> ConfigWrapper:
        config = super()._config.config_dict
        # Core TypedDict serializers inherit JSON options from the enclosing
        # serializer; their own ser_json_* settings are ignored by Pydantic.
        return ConfigWrapper(
            {
                **{
                    key: value
                    for key, value in config.items()
                    if not key.startswith("ser_json_")
                },
                **{
                    key: value
                    for key, value in self._json_configs[-1].items()
                    if key.startswith("ser_json_")
                },
            }
        )

    def model_schema(self, schema: Any) -> JsonSchemaValue:
        self._json_configs.append(schema.get("config", {}))
        try:
            return super().model_schema(schema)
        finally:
            self._json_configs.pop()

    def dataclass_schema(self, schema: Any) -> JsonSchemaValue:
        self._json_configs.append(schema.get("config", {}))
        try:
            return super().dataclass_schema(schema)
        finally:
            self._json_configs.pop()

    def _scoped_ref(self, schema: Any) -> str:
        if schema["type"] in ("model", "dataclass") and "serialization" not in schema:
            ref: str = schema["ref"]
            return ref
        config = self._config.config_dict
        # Shared types and model serializers can use different JSON configurations.
        # Pydantic otherwise reuses the first generated definition for all of them.
        key = repr(sorted((k, v) for k, v in config.items() if k.startswith("ser_json_")))
        context = self._contexts.setdefault(key, len(self._contexts))
        name, separator, identifier = schema["ref"].partition(":")
        return f"{name}__fast_depends_{context}{separator}{identifier}"

    def generate_inner(self, schema: Any) -> JsonSchemaValue:
        if schema["type"] == "definitions":
            # Register mutually recursive targets before generating any of them.
            self._definitions.update(
                {item["ref"]: item for item in schema["definitions"]}
            )
        elif "ref" in schema:
            self._definitions[schema["ref"]] = schema

        if schema["type"] == "definition-ref":
            target = self._definitions[schema["schema_ref"]]
            ref = self._scoped_ref(target)
            self._scoped_definitions[ref] = target
            schema = {**schema, "schema_ref": ref}
        elif "ref" in schema:
            ref = self._scoped_ref(schema)
            schema = {**schema, "ref": ref}
            self._generating.add(ref)
            try:
                return super().generate_inner(schema)
            finally:
                self._generating.remove(ref)
        return super().generate_inner(schema)

    def definition_ref_schema(self, schema: Any) -> JsonSchemaValue:
        ref = schema["schema_ref"]
        defs_ref = self.core_to_defs_refs.get((ref, self.mode))
        if ref not in self._generating and defs_ref not in self.definitions:
            self.generate_inner(self._scoped_definitions[ref])
        return super().definition_ref_schema(schema)

    if not hasattr(GenerateJsonSchema, "_common_temporal_schema"):
        # Pydantic 2.12/2.13 encode numeric temporal values, but their schema
        # generator predates support for ser_json_temporal.
        def _temporal_schema(self, schema: Any) -> JsonSchemaValue:
            result: JsonSchemaValue = getattr(super(), f"{schema['type']}_schema")(schema)
            config = self._config.config_dict
            temporal = config.get("ser_json_temporal")
            if temporal in ("seconds", "milliseconds"):
                result["type"] = "number"
                result.pop("format", None)
            elif temporal == "iso8601" and schema["type"] == "timedelta":
                result = {"type": "string", "format": "duration"}
            return result

        date_schema = time_schema = datetime_schema = timedelta_schema = _temporal_schema


def model_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema: dict[str, Any] = model.model_json_schema()
    return schema


def response_adapter(
    annotation: Any, config: ConfigDict
) -> tuple[TypeAdapter[Any], ConfigDict]:
    try:
        return TypeAdapter(annotation, config=config), config
    except PydanticUserError as error:
        if error.code != "type-adapter-config-unused":
            raise
        # Root models and Pydantic dataclasses can reuse their own serializer.
        # Its return serializers also use the class's JSON configuration.
        adapter = TypeAdapter(annotation)
        if adapter.serializer is getattr(annotation, "__pydantic_serializer__", None):
            config = cast(
                ConfigDict,
                getattr(
                    annotation,
                    "model_config",
                    getattr(annotation, "__pydantic_config__", {}),
                ),
            )
        else:
            config = ConfigDict()
        return adapter, config


def type_schema(adapter: TypeAdapter[Any], config: ConfigDict) -> dict[str, Any]:
    core_schema = adapter.core_schema
    generator = _ResponseSchema(config)
    # Before Pydantic 2.14, TypeAdapter.json_schema() does not forward config.
    with generator._config_wrapper_stack.push(config):
        schema: dict[str, Any] = generator.generate(core_schema, mode="serialization")
    return schema


def get_config_base(config_data: ConfigDict | None = None) -> ConfigDict:
    return config_data or ConfigDict(**default_pydantic_config)  # type: ignore[typeddict-item]


def get_schema_aliases(model: type[BaseModel]) -> dict[str, str]:
    aliases = {}
    # Inspect names before aliasing: a hidden field can share its alias with
    # a visible field or source, so aliased properties cannot identify it.
    properties = model.model_json_schema(by_alias=False).get("properties", {})
    serialization = model.model_config.get("json_schema_mode_override") == "serialization"
    for name, field in get_model_fields(model).items():
        if name not in properties:
            continue
        alias = field.serialization_alias if serialization else field.validation_alias
        if isinstance(alias, AliasChoices):
            alias = next(
                (
                    path[0]
                    for path in alias.convert_to_aliases()
                    if len(path) == 1 and isinstance(path[0], str)
                ),
                None,
            )
        # AliasPath cannot name a single JSON Schema property.
        aliases[name] = alias if isinstance(alias, str) else name
    return aliases


def get_aliases(model: type[BaseModel]) -> tuple[str, ...]:
    return tuple(f.alias or name for name, f in get_model_fields(model).items())


def get_model_fields(model: type[BaseModel]) -> dict[str, FieldInfo]:
    fields: dict[str, FieldInfo] | None = getattr(model, "__pydantic_fields__", None)

    if fields is not None:
        return fields

    # Deprecated in Pydantic V2.11 to be removed in V3.0.
    model_fields: dict[str, FieldInfo] = model.model_fields
    return model_fields


def dump_json(data: Any) -> bytes:
    return to_json(data)


def get_json_encoder(config: ConfigDict | None = None) -> Callable[[Any], bytes]:
    if not config:
        return dump_json
    # Match to_json() defaults unless a JSON encoding option is explicit.
    core_config = cast(CoreConfig, {"ser_json_inf_nan": "constants", **config})
    serializer = SchemaSerializer(any_schema(), config=core_config)
    return partial(serializer.to_json, by_alias=True)
