from copy import copy
from inspect import Parameter
from typing import Annotated

import pytest

pytest.importorskip("msgspec")
import msgspec

from fast_depends.library.serializer import OptionItem
from fast_depends.msgspec import MsgSpecSerializer


def make(*options, **config):
    return MsgSpecSerializer(**config)(
        name="handler", options=list(options), response_type=Parameter.empty
    )


def test_external_values_must_be_prepared_before_resolved_validation():
    serializer = make(OptionItem("value", int))
    serializer.prepare_fields()
    with pytest.raises(TypeError, match="must be prepared"):
        serializer.validate_resolved({"value": "1"})


def test_decode_hook_applies_once_to_shared_external_value():
    calls = []

    class Value:
        def __init__(self, value):
            self.value = value

    def decode(annotation, value):
        assert annotation is Value
        calls.append(value)
        return Value(int(value))

    serializer = make(OptionItem("value", Value), dec_hook=decode)
    field = serializer.prepare_fields()["value"]
    value = serializer.prepare_inputs([field])({"value": "1"})[field.key]
    assert serializer.validate_resolved({"value": value})["value"] is value.value
    assert value.value.value == 1
    assert calls == ["1"]


def test_shared_contract_normalizes_nested_native_constraints():
    first = make(
        OptionItem("values", list[Annotated[int, msgspec.Meta(gt=0, title="First")]])
    )
    second = make(
        OptionItem("values", list[Annotated[int, msgspec.Meta(gt=0, title="Second")]])
    )
    assert (
        first.prepare_fields()["values"].contract
        == second.prepare_fields()["values"].contract
    )


@pytest.mark.parametrize("paths", [(("body", "value"),), (("left",), ("right",))])
def test_native_input_contract_rejects_multiple_or_nested_aliases(paths):
    serializer = make()
    field = copy(make(OptionItem("value", int)).prepare_fields()["value"])
    field.paths = paths
    with pytest.raises(TypeError, match="require a single field alias"):
        serializer.prepare_inputs([field])


def test_native_input_contract_rejects_another_decode_hook():
    def decode(annotation, value):
        raise AssertionError("Incompatible hooks must not execute")

    first = make(OptionItem("value", int))
    second = make(OptionItem("value", int), dec_hook=decode)
    with pytest.raises(TypeError, match="Incompatible serializer"):
        first.prepare_inputs(list(second.prepare_fields().values()))
