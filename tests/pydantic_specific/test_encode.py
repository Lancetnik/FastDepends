from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import BaseModel

from fast_depends.pydantic.serializer import PydanticSerializer


class SimpleModel(BaseModel):
    r: str


@dataclass
class SimpleDataclass:
    r: str


now = datetime.now(timezone.utc)

parametrized = (
    pytest.param(
        "hello",
        b'"hello"',
        id="str",
    ),
    pytest.param(
        b"hello",
        b'"hello"',
        id="bytes",
    ),
    pytest.param(
        1.0,
        b"1.0",
        id="float",
    ),
    pytest.param(
        1,
        b"1",
        id="int",
    ),
    pytest.param(
        False,
        b"false",
        id="bool",
    ),
    pytest.param(
        {"m": 1},
        b'{"m":1}',
        id="dict",
    ),
    pytest.param(
        [1, 2, 3],
        b"[1,2,3]",
        id="list",
    ),
    pytest.param(
        SimpleDataclass(r="hello!"),
        b'{"r":"hello!"}',
        id="dataclass",
    ),
)


@pytest.mark.parametrize(
    ("message", "expected_message"),
    (
        *parametrized,
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
