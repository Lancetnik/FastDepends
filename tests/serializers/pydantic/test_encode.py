from datetime import datetime, timedelta
from typing import Annotated, Any

import pytest
from pydantic import BaseModel, PlainSerializer

from fast_depends import inject
from fast_depends.pydantic.serializer import PydanticSerializer
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
def test_encode(
    message: Any,
    expected_message: bytes,
) -> None:
    msg = PydanticSerializer.encode(message)
    assert msg == expected_message


@pytest.mark.parametrize(
    "config, message, expected",
    [
        ({"ser_json_timedelta": "float"}, timedelta(seconds=90), b"90.0"),
        ({"ser_json_temporal": "seconds"}, datetime(2026, 1, 1), b"1767225600.0"),
        ({"ser_json_bytes": "base64"}, {"data": b"\xff"}, b'{"data":"_w=="}'),
        ({"ser_json_bytes": "hex"}, [b"ab"], b'["6162"]'),
        ({"ser_json_inf_nan": "strings"}, float("inf"), b'"Infinity"'),
        ({"ser_json_inf_nan": "null"}, float("inf"), b"null"),
        (
            {"arbitrary_types_allowed": True},
            [float("inf"), float("nan"), float("-inf")],
            b"[Infinity,NaN,-Infinity]",
        ),
    ],
)
def test_instance_encode_uses_json_config(config, message, expected):
    assert PydanticSerializer(pydantic_config=config).encode(message) == expected


def test_configured_encoder_preserves_raw_bytes_and_class_calls():
    configured = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})

    assert configured.encode(b"\xff") == b"\xff"
    assert configured.encode([b"ab"]) == b'["YWI="]'
    assert PydanticSerializer.encode([b"ab"]) == b'["ab"]'
    assert PydanticSerializer.encode(message=[b"ab"]) == b'["ab"]'
    assert PydanticSerializer().encode([b"ab"]) == b'["ab"]'


def test_factory_preserves_subclass_encoder():
    class CustomSerializer(PydanticSerializer):
        @staticmethod
        def encode(message: Any) -> bytes:
            return b"custom"

    assert CustomSerializer().encode({"data": b"ab"}) == b"custom"


@pytest.mark.parametrize("wrapped", (True, False))
def test_json_config_does_not_change_injected_python_result(provider, wrapped):
    factory = PydanticSerializer(
        pydantic_config={"ser_json_timedelta": "float"},
        use_fastdepends_errors=wrapped,
    )

    @inject(serializer_cls=factory, dependency_provider=provider)
    def handler() -> timedelta:
        return timedelta(seconds=90)

    result = handler()

    assert result == timedelta(seconds=90)
    assert isinstance(result, timedelta)
    assert factory.encode(result) == b"90.0"


def test_json_config_does_not_enable_annotation_serializers(provider):
    factory = PydanticSerializer(pydantic_config={"ser_json_bytes": "base64"})
    annotation = Annotated[int, PlainSerializer(str, return_type=str)]

    @inject(serializer_cls=factory, dependency_provider=provider)
    def handler() -> annotation:
        return 42

    assert factory.encode(handler()) == b"42"


def test_json_config_preserves_model_owned_encoder():
    class Result(BaseModel):
        model_config = {"ser_json_bytes": "hex", "ser_json_timedelta": "iso8601"}
        data: bytes
        duration: timedelta

    factory = PydanticSerializer(
        pydantic_config={"ser_json_bytes": "base64", "ser_json_timedelta": "float"}
    )

    assert (
        factory.encode(
            [
                b"ab",
                timedelta(seconds=90),
                Result(data=b"ab", duration=timedelta(seconds=90)),
            ]
        )
        == b'["YWI=",90.0,{"data":"6162","duration":"PT1M30S"}]'
    )
