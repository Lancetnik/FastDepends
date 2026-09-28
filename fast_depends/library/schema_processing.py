"""Backend-independent JSON Schema transformations.

Only schema-valued keywords are traversed. Values such as defaults, examples,
constants and enum members are application data, even when they contain `$ref`.
"""

from collections.abc import Iterator
from copy import deepcopy
from typing import Any, TypeAlias
from urllib.parse import quote, unquote

SchemaExclude: TypeAlias = str | tuple[str | None, str]

_SCHEMA_MAPS = frozenset(
    {"properties", "patternProperties", "dependentSchemas", "dependencies"}
)
_SCHEMA_LISTS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})
_SCHEMA_VALUES = frozenset(
    {
        "additionalProperties",
        "additionalItems",
        "unevaluatedProperties",
        "unevaluatedItems",
        "propertyNames",
        "items",
        "contains",
        "not",
        "if",
        "then",
        "else",
        "contentSchema",
    }
)
_DEFINITIONS = ("$defs", "definitions")


def _children(
    schema: dict[str, Any], *, definitions: bool = False
) -> Iterator[dict[str, Any]]:
    for key, value in schema.items():
        if (key in _SCHEMA_MAPS or (definitions and key in _DEFINITIONS)) and isinstance(
            value, dict
        ):
            for child in value.values():
                if isinstance(child, dict):
                    yield child
        elif (key in _SCHEMA_LISTS or key == "items") and isinstance(value, list):
            for child in value:
                if isinstance(child, dict):
                    yield child
        elif key in _SCHEMA_VALUES and isinstance(value, dict):
            yield value


def _lookup(document: dict[str, Any], ref: str) -> dict[str, Any] | bool | None:
    if not ref.startswith("#"):
        return None
    pointer = unquote(ref[1:])
    if pointer and not pointer.startswith("/"):
        return None
    value: Any = document
    for token in pointer.split("/")[1:]:
        if value is not document and isinstance(value, dict) and "$id" in value:
            return None
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif isinstance(value, list) and token.isdigit() and int(token) < len(value):
            value = value[int(token)]
        else:
            return None
    return value if isinstance(value, (dict, bool)) else None


def _resolve(
    schema: dict[str, Any], document: dict[str, Any], active: frozenset[str]
) -> dict[str, Any]:
    result = deepcopy(schema)
    # A nested resource has its own reference scope. Do not resolve it against
    # the outer document or fetch its URI.
    if "$id" in result:
        return result
    for child in _children(result):
        processed = _resolve(child, document, active)
        child.clear()
        child.update(processed)
    ref = result.get("$ref")
    if isinstance(ref, str) and ref not in active:
        target = _lookup(document, ref)
        if target is not None and not (
            isinstance(target, dict)
            and any(key in target for key in ("$id", "$anchor", "$dynamicAnchor"))
        ):
            resolved: dict[str, Any] | bool = (
                _resolve(target, document, active | {ref})
                if isinstance(target, dict)
                else target
            )
            result.pop("$ref")
            if result:
                # A sibling constraint intersects the referenced schema. A dict
                # update would silently discard one side of that intersection.
                result = {**result, "allOf": [resolved, *result.get("allOf", [])]}
            elif isinstance(resolved, dict):
                return resolved
            else:
                return {"allOf": [resolved]}
    return result


def _references(schema: dict[str, Any]) -> Iterator[str]:
    for key in ("$ref", "$dynamicRef", "$recursiveRef"):
        ref = schema.get(key)
        if isinstance(ref, str):
            yield ref
    discriminator = schema.get("discriminator")
    if isinstance(discriminator, dict):
        for ref in discriminator.get("mapping", {}).values():
            if isinstance(ref, str):
                yield ref
    for child in _children(schema, definitions=True):
        yield from _references(child)


def _prune_definitions(schema: dict[str, Any]) -> None:
    pending = list(
        _references({k: v for k, v in schema.items() if k not in _DEFINITIONS})
    )
    used: set[tuple[str, str]] = set()
    while pending:
        ref = pending.pop()
        if not ref.startswith("#/"):
            # URI references may address an embedded $id resource. Root references
            # and anchors can also reach definitions without a JSON Pointer.
            return
        tokens = unquote(ref[2:]).split("/")
        if len(tokens) < 2 or tokens[0] not in _DEFINITIONS:
            continue
        key, name = tokens[0], tokens[1].replace("~1", "/").replace("~0", "~")
        if (key, name) in used:
            continue
        used.add((key, name))
        target = schema.get(key, {}).get(name)
        if isinstance(target, dict):
            pending.extend(_references(target))
    for key in _DEFINITIONS:
        if key in schema:
            retained = {
                name: value for name, value in schema[key].items() if (key, name) in used
            }
            if retained:
                schema[key] = retained
            else:
                schema.pop(key)


def _rebase_references(schema: dict[str, Any], prefix: str) -> None:
    if "$id" in schema:
        return
    for key in ("$ref", "$dynamicRef", "$recursiveRef"):
        ref = schema.get(key)
        if isinstance(ref, str) and (ref == "#" or ref.startswith("#/")):
            schema[key] = prefix + ref[1:]
    discriminator = schema.get("discriminator")
    if isinstance(discriminator, dict):
        mapping = discriminator.get("mapping", {})
        for name, ref in mapping.items():
            if isinstance(ref, str) and (ref == "#" or ref.startswith("#/")):
                mapping[name] = prefix + ref[1:]
    for child in _children(schema, definitions=True):
        _rebase_references(child, prefix)


def _embed(document: dict[str, Any]) -> dict[str, Any]:
    root = document
    root_ref = "#"
    seen: set[str] = set()
    while isinstance(ref := root.get("$ref"), str) and ref not in seen:
        seen.add(ref)
        target = _lookup(document, ref)
        if not isinstance(target, dict):
            break
        root, root_ref = target, ref
    properties = root.get("properties", {})
    if len(properties) != 1:
        return document
    name, value = next(iter(properties.items()))
    if isinstance(value, bool):
        # Keep the serializer's dict return type for both boolean schemas.
        value = {"allOf": [value]}
    # Moving a property normally only needs the document's global definitions.
    # Other local pointers/anchors still address the ORIGINAL input object. Keep
    # that object in a definition and point to its property instead of changing
    # the meaning of those references when the document root moves.
    preserve_root = (
        any(
            ref.startswith("#")
            and not any(unquote(ref).startswith(f"#/{key}/") for key in _DEFINITIONS)
            for ref in _references(document)
        )
        or any(
            key in value or key in document
            for key in ("$id", "$anchor", "$dynamicAnchor")
        )
        or any(key in value for key in _DEFINITIONS)
    )
    if preserve_root:
        prefix = "#/$defs/__fast_depends_input"
        original = deepcopy(document)
        _rebase_references(original, prefix)
        token = quote(name.replace("~", "~0").replace("/", "~1"), safe="~")
        return {
            "$ref": f"{prefix}{root_ref[1:]}/properties/{token}",
            "$defs": {"__fast_depends_input": original},
        }
    result: dict[str, Any] = deepcopy(value)
    for key in _DEFINITIONS:
        if key in document:
            result[key] = deepcopy(document[key])
    return result


def process_schema(
    schema: dict[str, Any], *, embed: bool = False, resolve_refs: bool = False
) -> dict[str, Any]:
    """Unwrap one input level and optionally inline acyclic local references.

    Recursive, external and unresolvable references remain references. Definitions
    used by surviving references or discriminator mappings stay in the document.
    The caller's schema (including a Pydantic v1 schema cache) is never modified.
    """
    if not embed and not resolve_refs:
        return schema
    document = deepcopy(schema)
    result = deepcopy(document)
    if embed:
        document = _embed(document)
        result = deepcopy(document)
    if resolve_refs:
        for key in _DEFINITIONS:
            result.pop(key, None)
        result = _resolve(result, document, frozenset())
        for key in _DEFINITIONS:
            if key in document:
                result[key] = deepcopy(document[key])
    _prune_definitions(result)
    return result
