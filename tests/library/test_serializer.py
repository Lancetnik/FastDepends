from inspect import Parameter
from typing import Any

import pytest

from fast_depends import Depends, Provider, inject
from fast_depends.exceptions import ValidationError
from fast_depends.library.serializer import (
    InputField,
    OptionItem,
    PreparedValue,
    Serializer,
    SerializerProto,
)


def _staged_factory(trace, paths=None):
    class StagedSerializer(Serializer):
        def __call__(self, values):
            trace.append("plain")
            return values

        def prepare_fields(self):
            return {
                name: InputField(
                    option,
                    key=(None, name),
                    paths=((name,),) if paths is None else paths,
                    required=True,
                    contract=option.field_type,
                    schema=None,
                )
                for name, option in self.options.items()
                if option.source is None
            }

        def prepare_inputs(self, fields):
            def prepare(values):
                trace.append("input")
                return {
                    field.key: PreparedValue(values[field.option.field_name])
                    for field in fields
                }

            return prepare

        def validate_resolved(self, values):
            trace.append("resolved")
            return {
                name: value.value if isinstance(value, PreparedValue) else value
                for name, value in values.items()
            }

    class Factory(SerializerProto):
        def __call__(self, **kwargs):
            return StagedSerializer(**kwargs)

    return Factory()


@pytest.mark.parametrize(
    "with_dependency", [pytest.param(False, id="plain"), pytest.param(True, id="depends")]
)
def test_custom_staged_serializer_supports_plain_and_dependency_calls(
    provider, with_dependency
):
    trace = []
    factory = _staged_factory(trace)

    if with_dependency:

        def dependency(value: int):
            return value * 2

        @inject(serializer_cls=factory, dependency_provider=provider)
        def handler(value: int, result: int = Depends(dependency)):
            return value + result

        expected = 6, ["input", "resolved", "resolved"]
    else:

        @inject(serializer_cls=factory, dependency_provider=provider)
        def handler(value: int):
            return value + 1

        expected = 3, ["plain"]

    assert (handler(2), trace) == expected


def test_custom_serializer_rejects_malformed_alias_during_preparation(provider):
    trace = []
    with pytest.raises(TypeError, match="alias must start with a name"):

        @inject(
            serializer_cls=_staged_factory(trace, paths=()), dependency_provider=provider
        )
        def handler(value: int): ...

    assert trace == []


@pytest.mark.parametrize(
    "backend",
    [pytest.param("pydantic", id="pydantic"), pytest.param("msgspec", id="msgspec")],
)
@pytest.mark.parametrize(
    "wrapped", [pytest.param(False, id="native"), pytest.param(True, id="wrapped")]
)
def test_native_resolved_stage_validates_computed_values(backend, wrapped):
    module = pytest.importorskip(backend)
    if backend == "pydantic":
        from fast_depends.pydantic import PydanticSerializer

        factory = PydanticSerializer(use_fastdepends_errors=wrapped)
    else:
        from fast_depends.msgspec import MsgSpecSerializer

        factory = MsgSpecSerializer(use_fastdepends_errors=wrapped)
    serializer = factory(
        name="handler",
        options=[OptionItem("result", int, source=object())],
        response_type=Parameter.empty,
    )
    assert serializer.validate_resolved({"result": "1"}) == {"result": 1}
    expected_error = ValidationError if wrapped else module.ValidationError
    with pytest.raises(expected_error):
        serializer.validate_resolved({"result": "invalid"})


def test_replaced_pydantic_argument_model_is_rejected_before_validation(provider):
    pytest.importorskip("pydantic")
    from pydantic import BaseModel, model_validator

    from fast_depends.pydantic import PydanticSerializer

    class ArgumentModel(BaseModel):
        value: int

        @model_validator(mode="before")
        @classmethod
        def validate_arguments(cls, value):
            raise AssertionError("An unsupported argument model must not validate")

    class CustomFactory(PydanticSerializer):
        def __call__(self, **kwargs):
            serializer = super().__call__(**kwargs)
            serializer.model = ArgumentModel
            return serializer

    with pytest.raises(TypeError, match="requires a generated argument model"):

        @inject(serializer_cls=CustomFactory(), dependency_provider=provider)
        def handler(value: int): ...


class EchoSerializer(Serializer):
    """A legacy serializer without staged validation hooks."""

    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("A legacy serializer must not execute during injection")


class EchoSerializerFactory(SerializerProto):
    def __call__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ) -> EchoSerializer:
        return EchoSerializer(
            name=name,
            options=options,
            response_type=response_type,
        )


def test_default_encode_uses_stdlib_json() -> None:
    assert EchoSerializerFactory.encode({"a": 1}) == b'{"a": 1}'


def test_default_get_aliases_is_empty() -> None:
    serializer = EchoSerializer(name="func", options=[], response_type=None)
    assert serializer.get_aliases() == ()


@pytest.mark.parametrize(
    "method", ["prepare_fields", "prepare_inputs", "validate_resolved"]
)
def test_legacy_serializer_staged_hooks_are_explicitly_unsupported(method):
    serializer = EchoSerializer(name="func", options=[], response_type=None)
    arguments = () if method == "prepare_fields" else ({},)
    with pytest.raises(TypeError, match="does not support"):
        getattr(serializer, method)(*arguments)


def test_legacy_serializer_requires_staged_validation() -> None:
    def dep() -> int:
        raise AssertionError("Incomplete serializers must not execute dependencies")

    with pytest.raises(TypeError, match="does not support staged input validation"):

        @inject(
            serializer_cls=EchoSerializerFactory(),
            dependency_provider=Provider(),
            cast_result=True,
        )
        def func(a: int, *, b: str = "b", d: int = Depends(dep)) -> str:
            raise AssertionError("Incomplete serializers must not execute handlers")


@pytest.mark.parametrize(
    "missing",
    [
        pytest.param("prepare_inputs", id="prepare-inputs"),
        pytest.param("validate_resolved", id="validate-resolved"),
    ],
)
def test_partial_staged_serializer_is_rejected_before_preparation(missing) -> None:
    class PartialSerializer(EchoSerializer):
        def prepare_fields(self):
            raise AssertionError("Incomplete serializers must not be prepared")

        def prepare_inputs(self, fields):
            raise AssertionError("Incomplete serializers must not be prepared")

        def validate_resolved(self, values):
            raise AssertionError("Incomplete serializers must not be prepared")

    class PartialFactory(EchoSerializerFactory):
        def __call__(self, **kwargs):
            return PartialSerializer(**kwargs)

    setattr(PartialSerializer, missing, getattr(Serializer, missing))
    with pytest.raises(TypeError, match=missing):

        @inject(serializer_cls=PartialFactory(), dependency_provider=Provider())
        def handler(value: int): ...


def test_argument_schema_is_optional_for_custom_serializers() -> None:
    serializer = EchoSerializer(name="func", options=[], response_type=None)

    with pytest.raises(NotImplementedError):
        serializer.get_schema()


def test_response_schema_is_optional_for_custom_serializers() -> None:
    serializer = EchoSerializer(name="func", options=[], response_type=None)

    with pytest.raises(NotImplementedError):
        serializer.get_response_schema()


def test_response_encoding_is_optional_for_custom_serializers() -> None:
    serializer = EchoSerializer(name="func", options=[], response_type=None)
    with pytest.raises(NotImplementedError):
        serializer.encode(None)
