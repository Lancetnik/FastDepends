from copy import deepcopy

import pytest
from dirty_equals import IsPartialDict

from fast_depends.library.schema_processing import process_schema


@pytest.mark.parametrize(
    "reference", ["#missing", "#/$defs/Missing", "#/$defs/Value/missing"]
)
def test_unresolvable_references_are_retained(reference):
    schema = {
        "properties": {"value": {"$ref": reference}},
        "$defs": {"Value": {"type": "integer"}},
    }

    assert process_schema(schema, resolve_refs=True)["properties"]["value"] == {
        "$ref": reference
    }


def test_reference_into_tuple_schema():
    schema = {
        "properties": {"value": {"$ref": "#/$defs/Tuple/prefixItems/0"}},
        "$defs": {
            "Tuple": {"type": "array", "prefixItems": [{"type": "integer"}, False]}
        },
    }

    assert process_schema(schema, resolve_refs=True)["properties"]["value"] == {
        "type": "integer"
    }


def test_reference_into_boolean_schema():
    schema = {
        "properties": {"value": {"$ref": "#/$defs/Denied"}},
        "$defs": {"Denied": False},
    }

    assert process_schema(schema, resolve_refs=True)["properties"]["value"] == {
        "allOf": [False]
    }


def test_reference_to_data_is_not_resolved():
    schema = {"properties": {"value": {"$ref": "#/title"}}, "title": "Input"}

    assert process_schema(schema, resolve_refs=True)["properties"]["value"] == {
        "$ref": "#/title"
    }


def test_embedded_external_root_stays_external():
    schema = {"$ref": "https://example.test/external"}

    assert process_schema(schema, embed=True, resolve_refs=True) == schema


def test_nested_resource_keeps_local_reference_scope():
    resource = {
        "$id": "https://example.test/resource",
        "$ref": "#/$defs/Local",
        "$defs": {"Local": {"type": "integer"}},
    }
    schema = {"properties": {"value": resource}, "$defs": {"Local": {"type": "string"}}}

    assert process_schema(schema, resolve_refs=True)["properties"]["value"] == resource


def test_anchor_reference_keeps_target_definition():
    schema = {
        "properties": {"value": {"$ref": "#value"}},
        "$defs": {"Value": {"$anchor": "value", "type": "integer"}},
    }

    assert process_schema(schema, resolve_refs=True) == schema


def test_embedding_preserves_named_resource():
    schema = {
        "$id": "https://example.test/resource",
        "properties": {"value": {"$ref": "#"}},
    }

    result = process_schema(schema, embed=True, resolve_refs=True)

    assert result["$defs"]["__fast_depends_input"] == schema


def test_embedding_rebases_discriminator_mapping():
    schema = {
        "properties": {
            "value": {
                "oneOf": [{"$ref": "#/$defs/A"}],
                "discriminator": {
                    "propertyName": "kind",
                    "mapping": {
                        "a": "#/$defs/A",
                        "external": "https://example.test/external",
                    },
                },
            }
        },
        "$defs": {"A": {"properties": {"child": {"$ref": "#"}}}},
    }

    result = process_schema(schema, embed=True, resolve_refs=True)

    assert result["discriminator"]["mapping"] == {
        "a": "#/$defs/__fast_depends_input/$defs/A",
        "external": "https://example.test/external",
    }


def test_schema_traversal_leaves_boolean_subschemas_intact():
    schema = {
        "allOf": [False, {"properties": {"value": False}}],
        "items": [False, {"type": "integer"}],
    }

    assert process_schema(schema, resolve_refs=True) == schema


def test_processing_does_not_mutate_input():
    schema = {
        "properties": {"value": {"$ref": "#/$defs/Value"}},
        "$defs": {"Value": {"type": "integer"}},
    }
    original = deepcopy(schema)

    process_schema(schema, embed=True, resolve_refs=True)

    assert schema == original


def test_reference_sibling_constraint_is_intersection():
    schema = {
        "properties": {"value": {"$ref": "#/$defs/Number", "maximum": 10}},
        "$defs": {"Number": {"type": "integer", "maximum": 5}},
    }

    assert process_schema(schema, embed=True, resolve_refs=True) == IsPartialDict(
        maximum=10, allOf=[IsPartialDict(maximum=5)]
    )


def test_non_reference_discriminator_metadata_is_preserved():
    schema = {"type": "object", "discriminator": {"mapping": {"unknown": None}}}

    assert process_schema(schema, resolve_refs=True) == schema


@pytest.mark.parametrize("reference", ["https://example.test/value", "value.json"])
@pytest.mark.parametrize("resolve_refs", [False, True])
def test_uri_reference_keeps_embedded_resource(reference, resolve_refs):
    resource = {"$id": reference, "type": "integer"}
    schema = {
        "properties": {"value": {"$ref": reference}},
        "$defs": {"Value": resource},
    }

    result = process_schema(schema, embed=True, resolve_refs=resolve_refs)

    assert result == {"$ref": reference, "$defs": {"Value": resource}}


@pytest.mark.parametrize("value", [False, True])
@pytest.mark.parametrize("resolve_refs", [False, True])
def test_embed_boolean_schema_keeps_dict_api(value, resolve_refs):
    schema = {"properties": {"value": value}}

    assert process_schema(schema, embed=True, resolve_refs=resolve_refs) == {
        "allOf": [value]
    }
