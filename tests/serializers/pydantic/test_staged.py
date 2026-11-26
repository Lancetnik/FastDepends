from inspect import Parameter
from typing import Annotated, Any, Literal

import pytest

pytest.importorskip("pydantic")
from pydantic import (
    AfterValidator,
    AliasChoices,
    AliasPath,
    BaseModel,
    BeforeValidator,
    Field,
    PlainValidator,
    WrapValidator,
    field_validator,
    model_validator,
)

from fast_depends.exceptions import ValidationError as FastDependsValidationError
from fast_depends.library.serializer import OptionItem
from fast_depends.pydantic import PydanticSerializer


def make(*options, config=None):
    return PydanticSerializer(config)(
        name="handler", options=list(options), response_type=Parameter.empty
    )


@pytest.mark.parametrize("kind", ["before", "wrap", "plain", "outer-wrap"])
def test_contextual_validation_uses_resolved_arguments(kind):
    def contextual(value, info):
        return int(value) + info.data.get("offset", 0)

    def wrap(value, handler, info):
        return handler(value) + info.data.get("offset", 0)

    def outer(value, handler):
        return handler(value) * 2

    validator = {
        "before": BeforeValidator(contextual),
        "wrap": WrapValidator(wrap),
        "plain": PlainValidator(contextual),
    }.get(kind)
    annotation = (
        Annotated[int, AfterValidator(contextual), WrapValidator(outer)]
        if kind == "outer-wrap"
        else Annotated[int, validator]
    )
    serializer = make(
        OptionItem("offset", int, source=object()), OptionItem("value", annotation)
    )
    field = serializer.prepare_fields()["value"]
    value = serializer.prepare_inputs([field])({"value": "1"})[field.key]
    assert serializer.validate_resolved({"offset": 10, "value": value})["value"] == (
        22 if kind == "outer-wrap" else 11
    )


def test_input_transform_is_not_repeated_before_contextual_after_validator():
    calls = []

    def prepare(value):
        calls.append(value)
        return value + 1

    def wrap(value, handler):
        return handler(value)

    def after(value, info):
        return value + info.data["offset"]

    annotation = Annotated[
        int,
        BeforeValidator(int),
        WrapValidator(wrap),
        AfterValidator(prepare),
        AfterValidator(after),
    ]
    serializer = make(
        OptionItem("offset", int, source=object()), OptionItem("value", annotation)
    )
    field = serializer.prepare_fields()["value"]
    value = serializer.prepare_inputs([field])({"value": "1"})[field.key]
    assert serializer.validate_resolved({"offset": 10, "value": value})["value"] == 12
    assert calls == [1]


def test_default_factory_reads_resolved_arguments():
    serializer = make(
        OptionItem("offset", int, source=object()),
        OptionItem(
            "value",
            int,
            default_value=Field(default_factory=lambda values: values["offset"] + 1),
        ),
        config={"validate_default": True},
    )
    assert serializer.prepare_inputs(list(serializer.prepare_fields().values()))({}) == {}
    assert serializer.validate_resolved({"offset": 10}) == {"offset": 10, "value": 11}


@pytest.mark.parametrize(
    "config,paths",
    [
        ({}, (("body", "value"), ("external",))),
        ({"validate_by_name": True}, (("body", "value"), ("external",), ("value",))),
        ({"validate_by_alias": False}, (("value",),)),
    ],
)
def test_alias_paths_follow_validation_config(config, paths):
    serializer = make(
        OptionItem(
            "value",
            int,
            default_value=Field(
                validation_alias=AliasChoices(AliasPath("body", "value"), "external")
            ),
        ),
        config=config,
    )
    field = serializer.prepare_fields()["value"]
    assert field.paths == paths
    values = (
        {"value": "1"}
        if config.get("validate_by_alias") is False
        else {"body": {"value": "1"}}
    )
    assert serializer.prepare_inputs([field])(values)[field.key].value == 1


def test_raw_resolved_arguments_use_native_validation():
    assert make(OptionItem("value", int)).validate_resolved({"value": "1"}) == {
        "value": 1
    }


def test_single_nested_alias_path_is_preserved():
    serializer = make(
        OptionItem(
            "value", int, default_value=Field(validation_alias=AliasPath("body", "value"))
        )
    )
    field = serializer.prepare_fields()["value"]
    assert field.paths == (("body", "value"),)
    assert (
        serializer.prepare_inputs([field])({"body": {"value": "1"}})[field.key].value == 1
    )


def test_input_contract_keeps_validation_and_omits_presentation_metadata():
    first = make(OptionItem("value", int, default_value=Field(gt=0, title="First")))
    second = make(OptionItem("value", int, default_value=Field(gt=0, title="Second")))
    assert (
        first.prepare_fields()["value"].contract
        == second.prepare_fields()["value"].contract
    )


def test_incompatible_validation_settings_are_rejected():
    first = make(OptionItem("value", int))
    second = make(OptionItem("value", int), config={"strict": True})
    with pytest.raises(TypeError, match="cannot mix Pydantic validation configurations"):
        first.prepare_inputs(list(second.prepare_fields().values()))


def test_empty_contract_still_enforces_forbidden_extra_values():
    serializer = make(config={"extra": "forbid"})
    with pytest.raises(FastDependsValidationError) as error:
        serializer.prepare_inputs([])({"extra": 1})
    assert error.value.__cause__.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("container", ["list", "union"])
def test_nested_contextual_scalar_validation_cannot_be_split(container):
    def contextual(value, info):
        raise AssertionError("Unsupported validation must not execute")

    Value = Annotated[int, AfterValidator(contextual)]
    serializer = make(
        OptionItem("values", list[Value] if container == "list" else str | Value)
    )
    with pytest.raises(TypeError, match="Cannot prepare input handler.values"):
        serializer.prepare_fields()


def test_replaced_argument_model_cannot_be_split():
    class Arguments(BaseModel):
        value: int

        @model_validator(mode="before")
        @classmethod
        def before(cls, value):
            raise AssertionError("The replaced argument model must not execute")

    serializer = make(OptionItem("value", int))
    serializer.model = Arguments
    with pytest.raises(TypeError, match="requires a generated argument model"):
        serializer.prepare_fields()


@pytest.fixture
def payload_model():
    calls = []

    class Payload(BaseModel):
        offset: int
        value: int
        metadata: dict[str, Any] = {"function": {"type": "with-info"}}

        @field_validator("value")
        @classmethod
        def add_offset(cls, value, info):
            calls.append((info.field_name, dict(info.data)))
            return value + info.data["offset"]

    return Payload, calls


def test_model_field_validators_receive_model_data_once(payload_model):
    Payload, calls = payload_model
    serializer = make(OptionItem("payload", Payload))
    field = serializer.prepare_fields()["payload"]
    prepared = serializer.prepare_inputs([field])(
        {"payload": {"offset": "2", "value": "3"}}
    )[field.key]
    first = serializer.validate_resolved({"payload": prepared})["payload"]
    second = serializer.validate_resolved({"payload": prepared})["payload"]
    assert first is second
    assert first.value == 5
    assert first.metadata == {"function": {"type": "with-info"}}
    assert calls == [("value", {"offset": 2})]


def test_model_validators_inside_tagged_union_receive_model_data(payload_model):
    Payload, calls = payload_model

    class First(Payload):
        kind: Literal["first"]

    class Second(Payload):
        kind: Literal["second"]

    annotation = Annotated[First | Second, Field(discriminator="kind")]
    serializer = make(OptionItem("payload", annotation))
    field = serializer.prepare_fields()["payload"]
    prepared = serializer.prepare_inputs([field])(
        {"payload": {"kind": "second", "offset": "2", "value": "3"}}
    )[field.key]
    assert prepared.value.value == 5
    assert calls == [("value", {"offset": 2})]


def test_recursive_model_validators_receive_model_data():
    calls = []

    class Node(BaseModel):
        value: int
        children: list["Node"] = Field(default_factory=list)

        @field_validator("value")
        @classmethod
        def record(cls, value, info):
            calls.append(info.field_name)
            return value + 1

    serializer = make(OptionItem("payload", Node))
    field = serializer.prepare_fields()["payload"]
    value = serializer.prepare_inputs([field])(
        {"payload": {"value": "1", "children": [{"value": "2"}]}}
    )[field.key].value
    assert (value.value, value.children[0].value) == (2, 3)
    assert calls == ["value", "value"]


def test_contextual_model_before_validator_cannot_be_split():
    class Payload(BaseModel):
        value: int

        @model_validator(mode="before")
        @classmethod
        def before(cls, value, info):
            raise AssertionError("Unsupported validation must not execute")

    with pytest.raises(TypeError, match="Cannot prepare input handler.payload"):
        make(OptionItem("payload", Payload)).prepare_fields()
