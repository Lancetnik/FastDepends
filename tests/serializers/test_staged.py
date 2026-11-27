from inspect import Parameter

import pytest

from fast_depends.exceptions import ValidationError
from fast_depends.library.serializer import OptionItem, Serializer


@pytest.fixture(params=["pydantic", "msgspec"])
def backend(request):
    module = pytest.importorskip(request.param)
    if request.param == "pydantic":
        from fast_depends.pydantic import PydanticSerializer

        return PydanticSerializer, module
    from fast_depends.msgspec import MsgSpecSerializer

    return MsgSpecSerializer, module


def make(factory, *options, **config):
    return factory(**config)(
        name="handler", options=list(options), response_type=Parameter.empty
    )


def test_input_values_are_converted_once_and_shared(backend):
    factory, module = backend
    alias = (
        module.Field(alias="items")
        if module.__name__ == "pydantic"
        else module.field(name="items")
    )
    first = make(factory, OptionItem("parent", list[int], default_value=alias))
    second = make(factory, OptionItem("child", list[int], default_value=alias))
    field = first.prepare_fields()["parent"]
    assert first.prepare_fields()["parent"] is field
    assert field.key == second.prepare_fields()["child"].key
    shared = first.prepare_inputs([field])({"items": ["1"]})[field.key]
    left = first.validate_resolved({"parent": shared})["parent"]
    right = second.validate_resolved({"child": shared})["child"]
    assert left == [1]
    assert left is right


def test_omitted_input_keeps_each_consumer_default(backend):
    factory, _ = backend
    first = make(factory, OptionItem("value", int, default_value=1))
    second = make(factory, OptionItem("value", int, default_value=2))
    fields = first.prepare_fields()
    assert first.prepare_inputs(list(fields.values()))({}) == {}
    assert first.validate_resolved({}) == {"value": 1}
    assert second.validate_resolved({}) == {"value": 2}


@pytest.mark.parametrize("wrapped", [False, True])
def test_native_errors_and_wrapped_errors_in_both_stages(backend, wrapped):
    factory, module = backend
    serializer = make(
        factory,
        OptionItem("value", int),
        OptionItem("result", int, source=object()),
        use_fastdepends_errors=wrapped,
    )
    field = serializer.prepare_fields()["value"]
    prepare = serializer.prepare_inputs([field])
    error = ValidationError if wrapped else module.ValidationError
    with pytest.raises(error):
        prepare({"value": "invalid"})
    value = prepare({"value": "1"})[field.key]
    with pytest.raises(error):
        serializer.validate_resolved({"value": value, "result": "invalid"})
    assert serializer.validate_resolved({"value": value, "result": "2"}) == {
        "value": 1,
        "result": 2,
    }


def test_empty_input_contract_allows_computed_values(backend):
    factory, _ = backend
    serializer = make(factory, OptionItem("value", int, source=object()))
    assert serializer.prepare_fields() == {}
    assert serializer.prepare_inputs([])({"unrelated": 1}) == {}
    assert serializer.validate_resolved({"value": "2"}) == {"value": 2}


def test_aliases_and_native_constraints_are_preserved(backend):
    factory, module = backend
    if module.__name__ == "pydantic":
        default = module.Field(alias="external", gt=0)
        annotation = int
    else:
        from typing import Annotated

        annotation = Annotated[int, module.Meta(gt=0)]
        default = module.field(name="external")
    serializer = make(factory, OptionItem("value", annotation, default_value=default))
    field = serializer.prepare_fields()["value"]
    assert field.paths == (("external",),)
    assert field.required
    prepare = serializer.prepare_inputs([field])
    assert serializer.validate_resolved(
        {"value": prepare({"external": "1"})[field.key]}
    ) == {"value": 1}
    with pytest.raises(ValidationError):
        prepare({"external": 0})


def test_omitted_inputs_defer_default_factories_until_resolved(backend):
    factory, module = backend
    calls = []

    def default_factory():
        calls.append("default")
        return []

    default = (
        module.Field(default_factory=default_factory)
        if module.__name__ == "pydantic"
        else module.field(default_factory=default_factory)
    )
    serializer = make(factory, OptionItem("items", list[int], default_value=default))
    assert serializer.prepare_inputs(list(serializer.prepare_fields().values()))({}) == {}
    assert calls == []
    first = serializer.validate_resolved({})["items"]
    second = serializer.validate_resolved({})["items"]
    assert first == second == []
    assert first is not second
    assert calls == ["default", "default"]


@pytest.mark.parametrize(
    "method", ["prepare_fields", "prepare_inputs", "validate_resolved"]
)
def test_legacy_serializers_explicitly_reject_staged_methods(method):
    class Legacy(Serializer):
        def __call__(self, values):
            return values

    serializer = Legacy(name="handler", options=[], response_type=Parameter.empty)
    assert serializer({"value": 1}) == {"value": 1}
    arguments = () if method == "prepare_fields" else ({},)
    with pytest.raises(TypeError, match="does not support"):
        getattr(serializer, method)(*arguments)
