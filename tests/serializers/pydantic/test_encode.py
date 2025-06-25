from typing import Any

import pytest
from pydantic import BaseModel

from fast_depends.pydantic.serializer import PydanticSerializer
from tests.marks import pydanticV2, pydanticV1
from tests.serializers.params import comptex_params, parametrized


class SimpleModel(BaseModel):
    r: str


@pytest.mark.parametrize(
    ("message", "expected_message"),
    (
        *parametrized,
        *comptex_params,
        pytest.param(
            SimpleModel(r="hello!"),
            b'{"r":"hello!"}',
            id="model",
        ),
    ),
)
@pydanticV2
def test_encode_v2(
    message: Any,
    expected_message: bytes,
) -> None:
    msg = PydanticSerializer.encode(message)
    assert msg == expected_message


@pytest.mark.parametrize(
    ("message", "expected_message"),
    (
        *parametrized,
        pytest.param(
            {"m": 1},
            b'{"m": 1}',
            id="dict",
        ),
        pytest.param(
            [1, 2, 3],
            b"[1, 2, 3]",
            id="list",
        ),
        pytest.param(
            b"hello",
            b'"hello"',
            id="bytes",
        ),
        pytest.param(
            SimpleModel(r="hello!"),
            b'{"r": "hello!"}',
            id="model",
        ),
    ),
)
@pydanticV1
def test_encode_v1(
    message: Any,
    expected_message: bytes,
) -> None:
    msg = PydanticSerializer.encode(message)
    assert msg == expected_message
