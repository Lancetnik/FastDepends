from collections.abc import Iterable
from typing import Any

from fast_depends.library.schema_processing import SchemaExclude
from fast_depends.library.serializer import OptionItem


class SchemaField(OptionItem):
    """An external input described by a CustomField, independent of runtime casting.

    ``source`` selects a named object under the schema's root properties.
    ``required=None`` preserves the backend's default-based requiredness.
    """

    __slots__ = ("required",)

    source: str | None

    def __init__(
        self,
        field_name: str,
        field_type: Any,
        *,
        default_value: Any = ...,
        source: str | None = None,
        required: bool | None = None,
    ) -> None:
        super().__init__(
            field_name=field_name,
            field_type=field_type,
            default_value=default_value,
            source=source,
        )
        self.required = required


def group_schema_fields(
    options: list[OptionItem],
) -> dict[str | None, list[OptionItem]]:
    groups: dict[str | None, list[OptionItem]] = {None: []}
    names: set[tuple[str | None, str]] = set()
    for option in options:
        source = option.source if isinstance(option, SchemaField) else None
        if source is not None and (not isinstance(source, str) or not source):
            raise ValueError("Schema field source must be a non-empty string or None")
        key = (source, option.field_name)
        if key in names:
            raise ValueError(
                f"Duplicate schema field {option.field_name!r} in source {source!r}"
            )
        names.add(key)
        groups.setdefault(source, []).append(option)
    return groups


def apply_schema_groups(
    schema: dict[str, Any],
    groups: dict[str | None, list[OptionItem]],
    aliases: dict[str | None, dict[str, str]],
) -> dict[str, Any]:
    """Apply requiredness after the backend has generated aliases and references."""

    def object_schema(value: dict[str, Any] | bool) -> dict[str, Any] | bool:
        if isinstance(value, bool):
            return value
        # Pydantic v1 decorates a reference with title/description by wrapping it.
        all_of = value.get("allOf", [])
        if len(all_of) == 1 and isinstance(all_of[0], dict) and "$ref" in all_of[0]:
            value = all_of[0]
        if "$ref" in value:
            ref = value["$ref"]
            target: Any = schema
            for key in ref[2:].split("/"):
                target = target[key.replace("~1", "/").replace("~0", "~")]
            value = target
        return value

    root = object_schema(schema)
    if isinstance(root, bool):
        return schema
    sources = [source for source in groups if source is not None]
    root_properties = root.get("properties", {})
    root_names = list(aliases[None].values()) + sources
    if len(set(root_names)) != len(root_names):
        raise ValueError("Conflicting schema field aliases or source names at the root")

    targets = {
        source: object_schema(root_properties[source])
        for source in sources
        if source in root_properties
    }
    for source, options in groups.items():
        if source is not None and source not in root_properties:
            continue
        target = root if source is None else targets[source]
        # A schema hook may replace the entire group. Preserve that schema and
        # its parent requiredness; there are no member properties to adjust.
        if isinstance(target, bool):
            continue
        properties = target.get("properties", {})
        field_aliases = aliases[source]
        if len(set(field_aliases.values())) != len(field_aliases):
            raise ValueError(f"Conflicting schema field aliases in source {source!r}")

        required = set(target.get("required", ()))
        for option in options:
            name = field_aliases.get(option.field_name)
            if name not in properties:
                continue
            if isinstance(option, SchemaField) and option.required is not None:
                if option.required:
                    required.add(name)
                else:
                    required.discard(name)

        if source is None:
            required.difference_update(
                source for source in sources if not isinstance(targets.get(source), bool)
            )
        if required:
            target["required"] = [name for name in properties if name in required]
        else:
            target.pop("required", None)

        if source is not None and required:
            root.setdefault("required", []).append(source)

    return schema


def exclude_schema_fields(
    options: list[OptionItem], exclude: Iterable[SchemaExclude]
) -> list[OptionItem]:
    """Exclude Python/description names before backend aliases are applied."""
    excluded = set(exclude)
    for item in excluded:
        if not isinstance(item, str) and not (
            isinstance(item, tuple)
            and len(item) == 2
            and (item[0] is None or isinstance(item[0], str))
            and isinstance(item[1], str)
        ):
            raise ValueError("Schema exclusions must be names or (source, field) pairs")
    result = []
    for option in options:
        source = option.source if isinstance(option, SchemaField) else None
        if (source, option.field_name) in excluded:
            continue
        if (option.field_name if source is None else source) in excluded:
            continue
        result.append(option)
    return result
