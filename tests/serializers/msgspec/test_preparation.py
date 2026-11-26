from inspect import Parameter

import pytest

pytest.importorskip("msgspec")

import msgspec

from fast_depends import Depends, inject
from fast_depends.core import build_call_model
from fast_depends.exceptions import ValidationError
from fast_depends.library.serializer import OptionItem
from fast_depends.msgspec import MsgSpecSerializer


def test_resolved_stage_requires_prepared_external_values():
    serializer = MsgSpecSerializer()(
        name="handler", options=[OptionItem("value", int)], response_type=Parameter.empty
    )
    serializer.prepare_fields()
    with pytest.raises(TypeError, match="must be prepared"):
        serializer.validate_resolved({"value": "1"})


def test_resolved_error_preserves_input_values(provider):
    def dependency():
        return "invalid"

    @inject(serializer_cls=MsgSpecSerializer(), dependency_provider=provider)
    def handler(value: int, result: int = Depends(dependency)):
        raise AssertionError("Invalid dependency results must not execute the handler")

    with pytest.raises(ValidationError) as error:
        handler(value="1")
    assert isinstance(error.value.__cause__, msgspec.ValidationError)


@pytest.mark.parametrize("wrapped", [False, True])
def test_standalone_serializer_rejects_shared_aliases(wrapped):
    serializer = MsgSpecSerializer(use_fastdepends_errors=wrapped)(
        name="handler",
        options=[
            OptionItem("first", int, default_value=msgspec.field(name="external")),
            OptionItem("second", int, default_value=msgspec.field(name="external")),
        ],
        response_type=Parameter.empty,
    )
    with pytest.raises(TypeError, match="require staged input preparation"):
        serializer({"external": 1})
    with pytest.raises(TypeError, match="require a bound call schema"):
        serializer.get_schema()


@pytest.mark.parametrize("factory", [False, True])
def test_shared_aliases_keep_each_consumer_default(provider, factory):
    def default(value):
        if factory:
            return msgspec.field(name="external", default_factory=lambda: value)
        return msgspec.field(name="external", default=value)

    @inject(serializer_cls=MsgSpecSerializer(), dependency_provider=provider)
    def handler(first: int = default(1), second: int = default(2)):  # noqa: B008
        return first, second

    assert handler() == (1, 2)


@pytest.mark.parametrize("nested", [False, True])
def test_shared_inputs_reject_foreign_backend(provider, nested):
    pytest.importorskip("pydantic")
    from pydantic import AliasPath, Field

    from fast_depends.pydantic import PydanticSerializer

    alias = Field(validation_alias=AliasPath("body", "value")) if nested else ...

    def handler(value: int = alias): ...

    other = build_call_model(
        handler, serializer_cls=PydanticSerializer(), dependency_provider=provider
    )
    serializer = MsgSpecSerializer()(
        name="handler", options=[], response_type=Parameter.empty
    )
    with pytest.raises(
        TypeError, match="single field alias" if nested else "Incompatible serializer"
    ):
        serializer.prepare_inputs(tuple(other.serializer.prepare_fields().values()))
