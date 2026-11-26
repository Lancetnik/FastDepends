from typing import Annotated, Literal

import pytest

pytest.importorskip("pydantic")
from pydantic import BaseModel, Field, field_validator, model_validator

from fast_depends import Depends, inject
from fast_depends.exceptions import ValidationError


@pytest.fixture
def payload_model():
    calls = []

    class Payload(BaseModel):
        offset: int
        value: int

        @field_validator("value")
        @classmethod
        def add_offset(cls, value, info):
            calls.append((info.field_name, dict(info.data)))
            return value + info.data["offset"]

    return Payload, calls


def test_model_field_validation_is_shared(provider, payload_model):
    Payload, calls = payload_model

    def dependency(value: Payload):
        return value

    @inject(dependency_provider=provider)
    def handler(value: Payload, result=Depends(dependency)):
        return value, result

    value, result = handler(value={"offset": "2", "value": "3"})
    assert value is result
    assert value.value == 5
    assert calls == [("value", {"offset": 2})]


def test_invalid_model_fails_before_dependencies(provider, payload_model):
    Payload, _ = payload_model

    def dependency():
        raise AssertionError("Invalid model input must fail before dependencies")

    @inject(dependency_provider=provider, extra_dependencies=(Depends(dependency),))
    def handler(value: Payload): ...

    with pytest.raises(ValidationError):
        handler(value={"offset": "2", "value": "invalid"})


def test_model_fields_inside_list_use_model_data(provider, payload_model):
    Payload, calls = payload_model

    @inject(dependency_provider=provider)
    def handler(values: list[Payload]):
        return values

    assert handler(values=[{"offset": "2", "value": "3"}])[0].value == 5
    assert calls == [("value", {"offset": 2})]


def test_recursive_model_field_validation_is_shared(provider):
    calls = []

    class Node(BaseModel):
        offset: int
        value: int
        children: list["Node"] = Field(default_factory=list)

        @field_validator("value")
        @classmethod
        def add_offset(cls, value, info):
            calls.append(info.data["offset"])
            return value + info.data["offset"]

    def dependency(value: Node):
        return value

    @inject(dependency_provider=provider)
    def handler(value: Node, result=Depends(dependency)):
        return value, result

    value, result = handler(
        value={"offset": "2", "value": "3", "children": [{"offset": "4", "value": "5"}]}
    )
    assert value is result
    assert (value.value, value.children[0].value) == (5, 9)
    assert calls == [2, 4]


def test_model_fields_inside_tagged_union_use_model_data(provider, payload_model):
    Payload, calls = payload_model

    class First(Payload):
        kind: Literal["first"]

    class Second(Payload):
        kind: Literal["second"]

    Value = Annotated[First | Second, Field(discriminator="kind")]

    @inject(dependency_provider=provider)
    def handler(value: Value):
        return value

    value = handler(value={"kind": "second", "offset": "2", "value": "3"})
    assert isinstance(value, Second)
    assert value.value == 5
    assert calls == [("value", {"offset": 2})]


def test_model_after_validator_uses_resolved_function_data(provider, payload_model):
    Payload, calls = payload_model
    contexts = []

    class Contextual(Payload):
        @model_validator(mode="after")
        def add_context(self, info):
            contexts.append(dict(info.data))
            return self.model_copy(
                update={"value": self.value + info.data.get("offset", 0)}
            )

    def dependency(value: Contextual):
        return value.value

    def offset():
        return 10

    @inject(dependency_provider=provider)
    def handler(
        offset: int = Depends(offset),
        value: Contextual = None,
        result=Depends(dependency),
    ):
        return value.value, result

    assert handler(value={"offset": "2", "value": "3"}) == (15, 5)
    assert calls == [("value", {"offset": 2})]
    assert contexts == [{}, {"offset": 10}]


def test_model_before_validator_with_outer_context_is_rejected(provider):
    class Payload(BaseModel):
        value: int

        @model_validator(mode="before")
        @classmethod
        def before(cls, value, info):
            raise AssertionError("An unsupported split must not execute validation")

    with pytest.raises(TypeError, match=r"Cannot prepare input handler\.value"):

        @inject(dependency_provider=provider)
        def handler(value: Payload): ...
