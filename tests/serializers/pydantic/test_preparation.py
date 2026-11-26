from contextlib import ExitStack
from typing import Annotated, Any

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
    ValidationError,
    WrapValidator,
)

from fast_depends import Depends, Provider, inject
from fast_depends.core import build_call_model
from fast_depends.library import CustomField
from fast_depends.pydantic import PydanticSerializer


def test_validate_default_keeps_consumer_defaults(provider):
    def dependency(value: int = 1):
        return value

    @inject(
        serializer_cls=PydanticSerializer({"validate_default": True}),
        dependency_provider=provider,
    )
    def handler(value: int = 2, result=Depends(dependency)):
        return value, result

    assert handler() == (2, 1)


def test_resolved_stage_uses_native_validation_for_raw_values():
    from inspect import Parameter

    from fast_depends.library.serializer import OptionItem

    serializer = PydanticSerializer()(
        name="handler", options=[OptionItem("value", int)], response_type=Parameter.empty
    )
    assert serializer.validate_resolved({"value": "1"}) == {"value": 1}


def test_alias_choices_bind_nested_positionals_without_mutation(provider):
    def dependency(): ...

    @inject(
        serializer_cls=PydanticSerializer({"validate_by_name": True}),
        dependency_provider=provider,
    )
    def handler(
        value: int = Field(
            validation_alias=AliasChoices(AliasPath("body", "items", -1), "external")
        ),
        resolved=Depends(dependency),
    ):
        return value

    body = {"items": []}
    assert handler("1", body=body) == 1
    assert body == {"items": []}
    assert handler(external="2") == 2
    assert handler(body={"items": ["3"]}) == 3
    assert handler(value="4") == 4
    assert handler("5") == 5
    with pytest.raises(TypeError, match="Multiple values"):
        handler("1", external="2")


def test_positional_alias_can_bind_inside_a_list_item(provider):
    def dependency(): ...

    @inject(dependency_provider=provider)
    def handler(
        value: int = Field(validation_alias=AliasPath("body", "items", 0, "value")),
        resolved=Depends(dependency),
    ):
        return value

    body = {"items": [{}]}
    assert handler("1", body=body) == 1
    assert body == {"items": [{}]}
    assert handler("2") == 2


def test_positional_alias_requires_a_container_when_combined_with_keywords(provider):
    @inject(dependency_provider=provider)
    def handler(
        value: Annotated[int, Field(validation_alias=AliasPath("body", "value"))],
    ):
        return value

    assert handler("1") == 1
    with pytest.raises(TypeError):
        handler("1", body=0)


def test_missing_alias_path_keeps_default_with_custom_field(provider):
    class Marker(CustomField):
        def use(self, **kwargs):
            kwargs[self.param_name] = None
            return kwargs

    @inject(dependency_provider=provider)
    def handler(
        value: Annotated[int, Field(validation_alias=AliasPath("body", "value"))] = 2,
        marker: Annotated[Any, Marker()] = None,
    ):
        return value

    assert handler() == 2


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("before", id="before"),
        pytest.param("wrap", id="wrap"),
        pytest.param("plain", id="plain"),
        pytest.param("outer-wrap", id="outer-wrap"),
    ],
)
def test_contextual_validators_use_resolved_node_arguments(provider, kind):
    def contextual(value, info):
        return int(value) + info.data.get("offset", 0)

    def wrap(value, handler, info):
        return handler(value) + info.data.get("offset", 0)

    def outer_wrap(value, handler):
        return handler(value) * 2

    validator = {
        "before": BeforeValidator(contextual),
        "wrap": WrapValidator(wrap),
        "plain": PlainValidator(contextual),
    }.get(kind)
    Value = (
        Annotated[int, AfterValidator(contextual), WrapValidator(outer_wrap)]
        if kind == "outer-wrap"
        else Annotated[int, validator]
    )

    def dependency(value: Value):
        return value

    def offset():
        return 10

    @inject(dependency_provider=provider)
    def handler(
        offset: int = Depends(offset), value: Value = 0, result=Depends(dependency)
    ):
        return value, result

    assert handler(value="1") == ((22, 2) if kind == "outer-wrap" else (11, 1))


def test_unsupported_nested_context_is_rejected_before_execution(provider):
    def contextual(value, info):
        raise AssertionError("Unsupported validation must not execute")

    Value = list[Annotated[int, AfterValidator(contextual)]]
    with pytest.raises(TypeError, match=r"Cannot prepare input handler\.items"):

        @inject(dependency_provider=provider)
        def handler(items: Value): ...


def test_literal_model_metadata_is_not_executed_as_validation(provider):
    class Payload(BaseModel):
        metadata: dict[str, Any] = {"function": {"type": "with-info"}}

    def dependency(): ...

    @inject(dependency_provider=provider)
    def handler(payload: Payload, resolved=Depends(dependency)):
        return payload.metadata

    assert handler({}) == {"function": {"type": "with-info"}}


def test_shared_bound_validator_is_compared_without_calling_it(provider):
    class Validator:
        def __init__(self):
            self.calls = 0

        def convert(self, value):
            self.calls += 1
            return int(value)

    validator = Validator()
    Parent = Annotated[int, BeforeValidator(validator.convert), Field(title="Parent")]
    Child = Annotated[int, BeforeValidator(validator.convert), Field(title="Child")]

    def dependency(value: Child):
        return value

    @inject(dependency_provider=provider)
    def handler(value: Parent, result=Depends(dependency)):
        return value, result

    assert validator.calls == 0
    assert handler("1") == (1, 1)
    assert validator.calls == 1


@pytest.mark.parametrize(
    "stage", [pytest.param("input", id="input"), pytest.param("resolved", id="resolved")]
)
def test_native_errors_are_preserved_in_both_stages(provider, stage):
    def dependency():
        return "invalid" if stage == "resolved" else 1

    @inject(
        serializer_cls=PydanticSerializer(use_fastdepends_errors=False),
        dependency_provider=provider,
    )
    def handler(value: int, resolved: int = Depends(dependency)):
        raise AssertionError("Invalid arguments must not execute the handler")

    with pytest.raises(ValidationError):
        handler(value="invalid" if stage == "input" else 1)


@pytest.mark.parametrize(
    "foreign_kind,error",
    [
        pytest.param(
            "config", "cannot mix Pydantic validation configurations", id="config"
        ),
        pytest.param(
            "backend", "cannot mix Pydantic validation configurations", id="backend"
        ),
        pytest.param("no-root", "require a root serializer", id="no-root"),
    ],
)
def test_foreign_serializer_is_rejected(provider, foreign_kind, error):
    def dependency(value: int):
        raise AssertionError("Incompatible configurations must not execute")

    def handler(result=Depends(dependency)):
        raise AssertionError("Incompatible configurations must not execute")

    model = build_call_model(
        handler,
        dependency_provider=provider,
        serializer_cls=None if foreign_kind == "no-root" else PydanticSerializer(),
    )
    foreign = Provider()
    if foreign_kind == "backend":
        pytest.importorskip("msgspec")
        from fast_depends.msgspec import MsgSpecSerializer

        factory = MsgSpecSerializer()
    else:
        factory = PydanticSerializer({"strict": True})
    foreign.add_dependant(
        build_call_model(
            dependency,
            dependency_provider=foreign,
            serializer_cls=factory,
        )
    )
    with ExitStack() as stack, pytest.raises(TypeError, match=error):
        model.solve(
            stack=stack, cache_dependencies={}, dependency_provider=foreign, value=1
        )


@pytest.mark.parametrize("nested", [False, True])
def test_overlapping_alias_choices_are_rejected(provider, nested):
    def alias(name):
        return AliasPath("body", name) if nested else name

    with pytest.raises(TypeError, match="Ambiguous external input.*shared"):

        @inject(dependency_provider=provider)
        def handler(
            first: int = Field(
                validation_alias=AliasChoices(alias("left"), alias("shared"))
            ),
            second: int = Field(
                validation_alias=AliasChoices(alias("right"), alias("shared"))
            ),
        ): ...


@pytest.mark.parametrize("parent_first", [False, True])
def test_parent_and_child_alias_paths_are_rejected(provider, parent_first):
    aliases = ["body", AliasPath("body", "value")]
    if not parent_first:
        aliases.reverse()
    with pytest.raises(TypeError, match=r"Overlapping input paths: handler\..*handler\."):

        @inject(dependency_provider=provider)
        def handler(
            first: Annotated[int, Field(validation_alias=aliases[0])],
            second: Annotated[int, Field(validation_alias=aliases[1])],
        ): ...


def test_parent_and_child_choices_for_one_input_are_rejected(provider):
    with pytest.raises(TypeError, match="Overlapping input paths"):

        @inject(dependency_provider=provider)
        def handler(
            value: Annotated[
                int,
                Field(validation_alias=AliasChoices("body", AliasPath("body", "value"))),
            ],
        ): ...


def test_schema_internal_names_preserve_native_alias_configuration(provider):
    def dependency(value: Annotated[int, Field(validation_alias="right", gt=0)]): ...

    def handler(
        value: Annotated[int, Field(validation_alias="left", gt=0)],
        result=Depends(dependency),
    ): ...

    model = build_call_model(
        handler,
        dependency_provider=provider,
        serializer_cls=PydanticSerializer({"alias_generator": str.upper}),
    )
    schema = model.serializer.get_schema()
    assert set(schema["properties"]) == {"left", "right"}
    assert schema["properties"]["right"]["exclusiveMinimum"] == 0


def test_alias_path_replacement_reaches_uncached_dependency(provider):
    class Replace(CustomField):
        def use(self, **kwargs):
            kwargs["body"] = {"value": 9}
            kwargs[self.param_name] = None
            return kwargs

    def dependency(value: int = Field(validation_alias=AliasPath("body", "value"))):
        return value

    def replace(changed=Replace()): ...  # noqa: B008

    @inject(dependency_provider=provider)
    def handler(
        before=Depends(dependency, use_cache=False),
        changed=Depends(replace),
        after=Depends(dependency, use_cache=False),
    ):
        return before, after

    assert handler(body={"value": 1}) == (1, 9)


def test_alias_path_mutation_uses_prepared_value(provider):
    class Append(CustomField):
        def use(self, **kwargs):
            kwargs["body"]["items"].append(9)
            kwargs[self.param_name] = None
            return kwargs

    def dependency(
        value: Annotated[list[int], Field(validation_alias=AliasPath("body", "items"))],
    ):
        return value

    def change(changed: Annotated[Any, Append()]): ...

    @inject(dependency_provider=provider)
    def handler(
        first=Depends(dependency, use_cache=False),
        changed=Depends(change),
        last=Depends(dependency, use_cache=False),
    ):
        return first, first is last

    body = {"items": ["1"]}
    assert handler(body=body) == ([1, 9], True)
    assert body == {"items": ["1"]}
