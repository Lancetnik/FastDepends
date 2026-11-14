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


def _raw_response_ref(ref: str) -> str:
    name, separator, identifier = ref.partition(":")
    return f"{name}__fast_depends_raw{separator}{identifier}"


def _raw_response_bytes(
    schema: Any,
    definitions: dict[str, Any] | None = None,
    seen: frozenset[str] = frozenset(),
) -> Any:
    """Mark bytes reachable without entering a JSON container or model."""
    definitions = definitions or {}
    kind = schema["type"]
    if kind == "definitions":
        definitions = {
            **definitions,
            **{item["ref"]: item for item in schema["definitions"]},
        }
    elif kind == "definition-ref":
        ref = schema["schema_ref"]
        if ref in seen:
            return {**schema, "schema_ref": _raw_response_ref(ref)}
        target = definitions[ref]
        result = _raw_response_bytes(target, definitions, seen | {ref})
        return schema if result is target else result
    elif kind == "bytes":
        result = {
            **schema,
            "metadata": {
                **schema.get("metadata", {}),
                "fast_depends_raw_bytes": True,
            },
        }
        if "ref" in result:
            result["ref"] = _raw_response_ref(result["ref"])
        return result

    fields = {
        "definitions": ("schema",),
        "nullable": ("schema",),
        "default": ("schema",),
        "function-before": ("schema",),
        "function-after": ("schema",),
        "function-wrap": ("schema",),
        "custom-error": ("schema",),
        "json": ("schema",),
        "json-or-python": ("json_schema", "python_schema"),
        "lax-or-strict": ("lax_schema", "strict_schema"),
    }.get(kind, ())
    changes = {}
    for field in fields:
        original = schema.get(field)
        if original is None:
            continue
        child = _raw_response_bytes(original, definitions, seen)
        if child is not original:
            changes[field] = child
    if kind == "union":
        choices = []
        for choice in schema["choices"]:
            child = choice[0] if isinstance(choice, tuple) else choice
            result = _raw_response_bytes(child, definitions, seen)
            choices.append((result, choice[1]) if isinstance(choice, tuple) else result)
            if result is not child:
                changes["choices"] = choices
    elif kind == "tagged-union":
        tagged_choices = {}
        for tag, choice in schema["choices"].items():
            result = _raw_response_bytes(choice, definitions, seen)
            tagged_choices[tag] = result
            if result is not choice:
                changes["choices"] = tagged_choices
    elif kind == "chain":
        child = _raw_response_bytes(schema["steps"][-1], definitions, seen)
        if child is not schema["steps"][-1]:
            changes["steps"] = [*schema["steps"][:-1], child]
    if not changes:
        return schema
    result = {**schema, **changes}
    # Nested uses of an alias retain their configured JSON representation.
    if "ref" in result:
        result["ref"] = _raw_response_ref(result["ref"])
    return result


class _ResponseSchema(GenerateJsonSchema):
    """Describe generic encoding of validated values, without a TypeAdapter."""

    _model_serializer = False
    _generic_refs: frozenset[str] = frozenset()

    def __init__(self, config: ConfigDict) -> None:
        self._json_config = {
            key: value for key, value in config.items() if key.startswith("ser_json_")
        }
        super().__init__()

    @property
    def _config(self) -> ConfigWrapper:
        config = super()._config
        if self._model_serializer:
            return config
        # Plain structures do not carry their adapter's encoding config.
        # Their JSON formats come from the factory, including when the type
        # itself declares __pydantic_config__.
        return ConfigWrapper(
            {
                **{
                    key: value
                    for key, value in config.config_dict.items()
                    if not key.startswith("ser_json_")
                },
                **self._json_config,
            }
        )

    def _get_alias_name(self, field: Any, name: str) -> str:
        if self._model_serializer:
            return super()._get_alias_name(field, name)
        # Plain dicts/dataclasses retain Python names after validation.
        return name

    @staticmethod
    def _generic_ref(ref: str) -> str:
        name, separator, identifier = ref.partition(":")
        return f"{name}__fast_depends_generic{separator}{identifier}"

    def bytes_schema(self, schema: Any) -> JsonSchemaValue:
        result = super().bytes_schema(schema)
        if not self._model_serializer:
            if schema.get("metadata", {}).get("fast_depends_raw_bytes"):
                result["format"] = "binary"
        return result

    if not hasattr(GenerateJsonSchema, "_common_temporal_schema"):
        # Pydantic 2.12/2.13 encode numeric temporal values, but their schema
        # generator predates support for ser_json_temporal.
        def _temporal_schema(self, schema: Any) -> JsonSchemaValue:
            result: JsonSchemaValue = getattr(super(), f"{schema['type']}_schema")(schema)
            if not self._model_serializer:
                temporal = self._json_config.get("ser_json_temporal")
                if temporal in ("seconds", "milliseconds"):
                    result["type"] = "number"
                    result.pop("format", None)
                elif temporal == "iso8601" and schema["type"] == "timedelta":
                    result = {"type": "string", "format": "duration"}
                elif (
                    schema["type"] == "timedelta"
                    and self._json_config.get("ser_json_timedelta") == "float"
                ):
                    result = {"type": "number"}
            return result

        date_schema = time_schema = datetime_schema = timedelta_schema = _temporal_schema

    def generate_inner(self, schema: Any) -> JsonSchemaValue:
        if self._model_serializer:
            return super().generate_inner(schema)

        cls = schema.get("cls")
        if schema["type"] in ("model", "dataclass") and hasattr(
            cls, "__pydantic_serializer__"
        ):
            # Models carry their own serializer into to_json(); an outer
            # Annotated serializer belongs only to the discarded adapter.
            self._model_serializer = True
            try:
                return super().generate_inner(cls.__pydantic_core_schema__)
            finally:
                self._model_serializer = False

        if schema["type"] == "definitions":
            # Mutually recursive definitions may refer to a later entry.
            self._generic_refs |= {
                definition["ref"]
                for definition in schema["definitions"]
                if not (
                    definition["type"] in ("model", "dataclass")
                    and hasattr(definition.get("cls"), "__pydantic_serializer__")
                )
            }

        if "ref" in schema:
            schema = schema.copy()
            ref = schema["ref"]
            self._generic_refs |= {ref}
            # Model serializers may apply different aliases and JSON formats
            # to the same type, including named scalar aliases.
            schema["ref"] = self._generic_ref(ref)
        elif (
            schema["type"] == "definition-ref"
            and schema["schema_ref"] in self._generic_refs
        ):
            schema = schema.copy()
            schema["schema_ref"] = self._generic_ref(schema["schema_ref"])

        if "serialization" in schema:
            schema = schema.copy()
            schema.pop("serialization")
        return super().generate_inner(schema)


def model_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema: dict[str, Any] = model.model_json_schema()
    return schema


def type_schema(annotation: Any, config: ConfigDict) -> dict[str, Any]:
    try:
        adapter = TypeAdapter(annotation, config=config)
    except PydanticUserError:
        adapter = TypeAdapter(annotation)
    generator = _ResponseSchema(config)
    # Before Pydantic 2.14, TypeAdapter.json_schema() does not forward its
    # config to the generator. Match the configured generic JSON encoder.
    with generator._config_wrapper_stack.push(config):
        schema: dict[str, Any] = generator.generate(
            _raw_response_bytes(adapter.core_schema), mode="serialization"
        )
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
