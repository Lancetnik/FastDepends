from typing import Any

import pytest
from pydantic import BaseModel

from fast_depends.pydantic.serializer import PydanticSerializer
from tests.serializers.params import parametrized


class SimpleModel(BaseModel):
    r: str


@pytest.mark.parametrize(
    ("message", "expected_message"),
    (
        *parametrized,
        pytest.param(
            b"hello",
            b'"hello"',
            id="bytes",
        ),
        pytest.param(
            SimpleModel(r="hello!"),
            b'{"r":"hello!"}',
            id="model",
        ),
    ),
)
def test_encode(
    message: Any,
    expected_message: bytes,
) -> None:
    msg = PydanticSerializer.encode(message)
    assert msg == expected_message
