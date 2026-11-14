from datetime import timedelta

import pytest

from fast_depends.pydantic import PydanticSerializer
from tests.marks import pydanticV2


@pydanticV2
@pytest.mark.parametrize(
    "config, annotation, value, encoded, schema",
    [
        ({}, int, "42", b"42", {"type": "integer"}),
        (
            {},
            list[bytes],
            [b"ab"],
            b'["ab"]',
            {"type": "array", "items": {"type": "string", "format": "binary"}},
        ),
        (
            {"ser_json_bytes": "base64"},
            bytes,
            b"\xff",
            b"\xff",
            {"type": "string", "format": "binary"},
        ),
        (
            {"ser_json_bytes": "base64"},
            list[bytes],
            [b"\xff"],
            b'["_w=="]',
            {"type": "array", "items": {"type": "string", "format": "base64url"}},
        ),
        (
            {"ser_json_timedelta": "float"},
            timedelta,
            timedelta(seconds=90),
            b"90.0",
            {"type": "number"},
        ),
    ],
)
def test_response_schema_encoding_compatibility(
    config, annotation, value, encoded, schema
):
    factory = PydanticSerializer(pydantic_config=config)
    serializer = factory(name="handler", options=[], response_type=annotation)

    assert factory.encode(serializer.response(value)) == encoded
    assert serializer.get_response_schema() == schema
