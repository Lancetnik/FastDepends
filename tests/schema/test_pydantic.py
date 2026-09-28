from copy import deepcopy
from inspect import Parameter
from typing import Annotated, Any, Literal
from unittest.mock import Mock

import pytest
from dirty_equals import IsPartialDict

pytest.importorskip("pydantic")

from pydantic import BaseModel, Field, Json

from fast_depends import Depends, inject
from fast_depends.library.serializer import OptionItem
from fast_depends.pydantic import PydanticSerializer
from fast_depends.pydantic._compat import PYDANTIC_V2
from tests.marks import pydanticV1, pydanticV2
from tests.schema.custom_fields import Input, source_schema

if PYDANTIC_V2:
    from pydantic import AliasChoices, AliasPath
    from pydantic.json_schema import SkipJsonSchema


class Node(BaseModel):
    children: list["Node"] = Field(default_factory=list)


def test_bound_schema_preserves_config(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(pydantic_config={"extra": "forbid"}),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(count: int): ...

    assert capture.serializer.get_schema() == IsPartialDict(additionalProperties=False)


def test_bound_schema_preserves_dependency_alias(capture, provider):
    def dependency(count: int = Field(..., alias="size")): ...

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert capture.serializer.get_schema() == IsPartialDict(
        properties={"size": IsPartialDict(type="integer")}, required=["size"]
    )


def test_bound_schema_preserves_dependency_constraints(capture, provider):
    def dependency(count: int = Field(..., gt=0)): ...

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert capture.serializer.get_schema() == IsPartialDict(
        properties={"count": IsPartialDict(exclusiveMinimum=0)}
    )


def test_bound_schema_preserves_default_factory(capture, provider):
    def dependency(values: list[int] = Field(default_factory=list)): ...

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert not capture.serializer.get_schema().get("required")


@pydanticV2
def test_bound_schema_uses_validation_mode(capture, provider):
    def dependency(value: Json[int]): ...

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    assert capture.serializer.get_schema() == IsPartialDict(
        properties={"value": IsPartialDict(type="string")}
    )


def test_bound_schema_preserves_recursive_references(capture, provider):
    def dependency(node: Node): ...

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Any = Depends(dependency)): ...

    ref_key = "$defs" if PYDANTIC_V2 else "definitions"
    assert capture.serializer.get_schema() == IsPartialDict(
        {
            "properties": {"node": {"$ref": f"#/{ref_key}/Node"}},
            ref_key: {
                "Node": IsPartialDict(
                    properties={
                        "children": IsPartialDict(items={"$ref": f"#/{ref_key}/Node"})
                    }
                )
            },
        }
    )


def test_custom_field_preserves_alias(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        value: Annotated[int, Input("headers")] = Field(..., alias="x-value"),
    ): ...

    assert source_schema(capture.serializer.get_schema(), "headers") == IsPartialDict(
        properties={"x-value": IsPartialDict(type="integer")}, required=["x-value"]
    )


def test_uncast_custom_field_preserves_annotated_constraints(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Annotated[int, Input("query", cast=False), Field(gt=0)]): ...

    assert source_schema(capture.serializer.get_schema(), "query") == IsPartialDict(
        properties={"value": IsPartialDict(type="integer", exclusiveMinimum=0)}
    )


def test_custom_field_preserves_default_factory(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        values: Annotated[list[int], Input("query")] = Field(default_factory=list),
    ): ...

    assert not source_schema(capture.serializer.get_schema(), "query").get("required")


def test_custom_field_schema_does_not_run_default_factory(capture, provider):
    factory = Mock(return_value=[])

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        values: Annotated[list[int], Input("query")] = Field(default_factory=factory),
    ): ...

    capture.serializer.get_schema()

    factory.assert_not_called()


def test_custom_field_group_preserves_config(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(pydantic_config={"extra": "forbid"}),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Annotated[int, Input("query")]): ...

    assert source_schema(capture.serializer.get_schema(), "query") == IsPartialDict(
        additionalProperties=False
    )


def test_custom_field_group_preserves_alias_generator(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(pydantic_config={"alias_generator": str.upper}),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Annotated[int, Input("query")]): ...

    assert source_schema(capture.serializer.get_schema(), "query") == IsPartialDict(
        properties={"VALUE": IsPartialDict(type="integer")}, required=["VALUE"]
    )


def test_custom_field_alias_collision_fails(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        first: Annotated[int, Input("headers")] = Field(..., alias="value"),
        second: Annotated[str, Input("headers")] = Field(..., alias="value"),
    ): ...

    with pytest.raises(ValueError, match="Conflicting schema field aliases.*headers"):
        capture.serializer.get_schema()


def test_root_alias_conflicting_with_source_fails(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        value: Annotated[str, Input("headers")],
        plain: int = Field(..., alias="headers"),
    ): ...

    with pytest.raises(
        ValueError, match="Conflicting schema field aliases or source names"
    ):
        capture.serializer.get_schema()


def test_custom_field_preserves_recursive_references(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(node: Annotated[Node, Input("query")]): ...

    schema = capture.serializer.get_schema()
    ref_key = "$defs" if PYDANTIC_V2 else "definitions"

    assert {"group": source_schema(schema, "query"), "node": schema[ref_key]["Node"]} == {
        "group": IsPartialDict(properties={"node": {"$ref": f"#/{ref_key}/Node"}}),
        "node": IsPartialDict(
            properties={"children": IsPartialDict(items={"$ref": f"#/{ref_key}/Node"})}
        ),
    }


@pydanticV2
def test_custom_field_validation_alias(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        value: Annotated[int, Input("headers")] = Field(validation_alias="x-value"),
    ): ...

    assert source_schema(capture.serializer.get_schema(), "headers") == IsPartialDict(
        properties={"x-value": IsPartialDict(type="integer")}, required=["x-value"]
    )


def sort_schema_properties(schema):
    schema["properties"] = dict(sorted(schema["properties"].items()))


@pytest.mark.parametrize("source", [None, "query"])
def test_custom_requiredness_uses_aliases_after_property_reordering(
    capture, provider, source
):
    config_key = "json_schema_extra" if PYDANTIC_V2 else "schema_extra"

    @inject(
        serializer_cls=PydanticSerializer(
            pydantic_config={config_key: sort_schema_properties}
        ),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        first: Annotated[int, Input(source, required=False)] = Field(
            ..., alias="z_optional"
        ),
        second: Annotated[int, Input(source)] = Field(..., alias="a_required"),
    ): ...

    schema = capture.serializer.get_schema()
    target = schema if source is None else source_schema(schema, source)

    assert target["required"] == ["a_required"]


@pydanticV2
@pytest.mark.parametrize("source", [None, "query"])
def test_custom_field_allows_schema_hidden_fields(capture, provider, source):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        hidden: SkipJsonSchema[int],
        custom_hidden: Annotated[SkipJsonSchema[int], Input(source)],
        visible: Annotated[int, Input(source, required=False)],
    ): ...

    schema = capture.serializer.get_schema()
    target = schema if source is None else source_schema(schema, source)

    assert target == IsPartialDict(properties={"visible": IsPartialDict(type="integer")})


@pydanticV2
def test_hidden_root_alias_does_not_conflict_with_source(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        value: Annotated[int, Input("headers")],
        raw_headers: SkipJsonSchema[dict[str, int]] = Field(alias="headers"),
    ):
        return value

    assert handler(headers={"value": 3}) == 3
    assert source_schema(capture.serializer.get_schema(), "headers") == IsPartialDict(
        properties={"value": IsPartialDict(type="integer")}, required=["value"]
    )


@pydanticV2
@pytest.mark.parametrize("source", [None, "headers"])
@pytest.mark.parametrize("hidden_first", [True, False])
@pytest.mark.parametrize("required", [True, False])
def test_hidden_alias_does_not_change_visible_requiredness(
    capture, provider, source, hidden_first, required
):
    hidden = Annotated[SkipJsonSchema[int], Input(source, required=not required)]
    visible = Annotated[int, Input(source, required=required)]

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        first: hidden if hidden_first else visible = Field(alias="value"),
        second: visible if hidden_first else hidden = Field(alias="value"),
    ): ...

    schema = capture.serializer.get_schema()
    target = schema if source is None else source_schema(schema, source)
    assert target.get("required", []) == (["value"] if required else [])


@pydanticV2
@pytest.mark.parametrize(
    "alias, expected",
    [
        (AliasChoices("external", "fallback") if PYDANTIC_V2 else None, "external"),
        (AliasPath("outer", "inner") if PYDANTIC_V2 else None, "value"),
        (
            AliasChoices(AliasPath("external"), "fallback") if PYDANTIC_V2 else None,
            "external",
        ),
    ],
)
def test_custom_requiredness_uses_validation_alias(capture, provider, alias, expected):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        value: Annotated[int, Input("query", required=False)] = Field(
            validation_alias=alias
        ),
    ): ...

    assert source_schema(capture.serializer.get_schema(), "query") == (
        IsPartialDict(properties={expected: IsPartialDict(type="integer")})
        & ~IsPartialDict(required=[expected])
    )


@pytest.mark.parametrize("embed", [False, True])
def test_resolve_recursive_schema_keeps_definition(capture, provider, embed):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(node: Node): ...

    schema = capture.serializer.get_schema(embed=embed, resolve_refs=True)
    key = "$defs" if PYDANTIC_V2 else "definitions"

    assert schema[key]["Node"]["properties"]["children"]["items"] == {
        "$ref": f"#/{key}/Node"
    }


def test_embed_keeps_unresolved_definition(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(node: Node): ...

    schema = capture.serializer.get_schema(embed=True)
    key = "$defs" if PYDANTIC_V2 else "definitions"

    assert schema["$ref"] == f"#/{key}/Node" and "Node" in schema[key]


def test_exclusion_uses_python_name_before_alias(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: int = Field(..., alias="external")): ...

    assert capture.serializer.get_schema(exclude=("value",)) == IsPartialDict(
        properties={}
    )


def test_exclusion_uses_described_name_before_alias(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(
        value: Annotated[int, Input("query", name="described")] = Field(
            ..., alias="external"
        ),
    ): ...

    assert capture.serializer.get_schema(
        exclude=(("query", "described"),)
    ) == IsPartialDict(properties={})


def test_processing_preserves_standalone_schema_cache():
    serializer = PydanticSerializer()(
        name="handler", options=[OptionItem("node", Node)], response_type=Parameter.empty
    )
    original = deepcopy(serializer.get_schema())

    serializer.get_schema(embed=True, resolve_refs=True)

    assert serializer.get_schema() == original


class Cat(BaseModel):
    kind: Literal["cat"]


class Dog(BaseModel):
    kind: Literal["dog"]


def test_resolve_preserves_discriminator_targets(capture, provider):
    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(pet: Annotated[Cat | Dog, Field(discriminator="kind")]): ...

    schema = capture.serializer.get_schema(resolve_refs=True, embed=True)
    key = "$defs" if PYDANTIC_V2 else "definitions"

    assert {
        ref.rsplit("/", 1)[-1] for ref in schema["discriminator"]["mapping"].values()
    } <= schema[key].keys()


def hide_headers(schema):
    schema.get("properties", {}).pop("headers", None)


def test_schema_extra_can_hide_source_group(capture, provider):
    config_key = "json_schema_extra" if PYDANTIC_V2 else "schema_extra"

    @inject(
        serializer_cls=PydanticSerializer(pydantic_config={config_key: hide_headers}),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: Annotated[int, Input("headers")]): ...

    assert capture.serializer.get_schema() == IsPartialDict(properties={})


@pytest.fixture(params=["title", "description"])
def decorated_group_schema(request, capture, provider):
    def make_schema(required):
        @inject(
            serializer_cls=PydanticSerializer(
                pydantic_config={"fields": {"source_1": {request.param: "Headers"}}}
            ),
            dependency_provider=provider,
            wrap_model=capture,
        )
        def handler(token: Annotated[str, Input("headers", required=required)]): ...

        return capture.serializer.get_schema()

    return make_schema


@pydanticV1
@pytest.mark.parametrize("required", [True, False])
def test_group_documentation_preserves_root_requiredness(
    decorated_group_schema, required
):
    schema = decorated_group_schema(required)

    assert schema.get("required", []) == (["headers"] if required else [])


@pydanticV1
@pytest.mark.parametrize("required", [True, False])
def test_group_documentation_preserves_field_requiredness(
    decorated_group_schema, required
):
    schema = decorated_group_schema(required)
    ref = schema["properties"]["headers"]["allOf"][0]["$ref"]
    target = schema["definitions"][ref.split("/")[-1]]

    assert target.get("required", []) == (["token"] if required else [])


@pytest.mark.parametrize("value", [True, False])
def test_boolean_source_group_preserves_native_schema(capture, provider, value):
    def replace_group(schema):
        if "headers" in schema.get("properties", {}):
            schema["properties"]["headers"] = value

    config_key = "json_schema_extra" if PYDANTIC_V2 else "schema_extra"

    @inject(
        serializer_cls=PydanticSerializer(pydantic_config={config_key: replace_group}),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(token: Annotated[str, Input("headers")]): ...

    assert capture.serializer.get_schema() == IsPartialDict(
        properties={"headers": value}, required=["headers"]
    )


@pytest.mark.parametrize("value", [False, True])
def test_embed_boolean_property_from_schema_extra(capture, provider, value):
    config_key = "json_schema_extra" if PYDANTIC_V2 else "schema_extra"

    @inject(
        serializer_cls=PydanticSerializer(
            pydantic_config={config_key: {"properties": {"value": value}}}
        ),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler(value: int): ...

    assert capture.serializer.get_schema(embed=True) == {"allOf": [value]}
