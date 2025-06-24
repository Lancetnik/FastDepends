from typing import Any

import pytest
from msgspec import Struct

from fast_depends.msgspec.serializer import MsgSpecSerializer
from tests.serializers.params import parametrized


class SimpleStruct(Struct):
    r: str


@pytest.mark.parametrize(
    ("message", "expected_message"),
    (
        *parametrized,
        pytest.param(
            b"hello",
            b'"aGVsbG8="',
            id="bytes",
        ),
        pytest.param(
            SimpleStruct(r="hello!"),
            b'{"r":"hello!"}',
            id="struct",
        ),
    ),
)
def test_encode(
    message: Any,
    expected_message: bytes,
) -> None:
    msg = MsgSpecSerializer.encode(message)
    assert msg == expected_message
