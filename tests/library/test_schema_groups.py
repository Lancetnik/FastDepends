import pytest

from fast_depends.library.schema import apply_schema_groups


@pytest.mark.parametrize("value", [True, False])
def test_boolean_root_reference_is_preserved(value):
    schema = {"$ref": "#/definitions/root", "definitions": {"root": value}}

    assert apply_schema_groups(schema, {None: []}, {None: {}}) == schema
