from inspect import Parameter
from typing import Annotated

import pytest
from dirty_equals import IsPartialDict

from fast_depends.library.serializer import OptionItem
from tests.schema.custom_fields import Input, source_schema
from tests.serializers.test_schema import resolve_root


def test_exclude_root_field(schema_inject, capture):
    @schema_inject
    def handler(first: int, second: str): ...

    assert resolve_root(
        capture.serializer.get_schema(exclude=("first",))
    ) == IsPartialDict(
        properties={"second": IsPartialDict(type="string")}, required=["second"]
    )


def test_exclude_all_inputs_remains_object(schema_inject, capture):
    @schema_inject
    def handler(value: int): ...

    assert resolve_root(
        capture.serializer.get_schema(exclude=("value",))
    ) == IsPartialDict(type="object", properties={})


def test_exclude_named_source(schema_inject, capture):
    @schema_inject
    def handler(value: int, token: Annotated[str, Input("headers")]): ...

    assert resolve_root(
        capture.serializer.get_schema(exclude=("headers",))
    ) == IsPartialDict(
        properties={"value": IsPartialDict(type="integer")}, required=["value"]
    )


def test_exclude_source_field_keeps_other_sources(schema_inject, capture):
    @schema_inject
    def handler(
        value: int,
        header: Annotated[int, Input("headers", name="value")],
        query: Annotated[int, Input("query", name="value")],
    ): ...

    schema = capture.serializer.get_schema(exclude=(("headers", "value"),))

    assert list(resolve_root(schema)["properties"]) == ["value", "query"]


def test_exclude_last_required_source_field(schema_inject, capture):
    @schema_inject
    def handler(
        token: Annotated[str, Input("headers")],
        limit: Annotated[int, Input("headers", required=False)],
    ): ...

    assert not resolve_root(
        capture.serializer.get_schema(exclude=(("headers", "token"),))
    ).get("required")


def test_root_exclusion_does_not_match_source_field(schema_inject, capture):
    @schema_inject
    def handler(value: int, custom: Annotated[int, Input("query", name="value")]): ...

    schema = capture.serializer.get_schema(exclude=("value",))

    assert source_schema(schema, "query") == IsPartialDict(
        properties={"value": IsPartialDict(type="integer")}
    )


def test_exclusion_does_not_change_runtime(schema_inject, capture):
    @schema_inject
    def handler(value: int):
        return value

    capture.serializer.get_schema(exclude=("value",))

    assert handler(value="12") == 12


def test_exclusion_does_not_change_next_schema(schema_inject, capture):
    @schema_inject
    def handler(value: int): ...

    capture.serializer.get_schema(exclude=("value",))

    assert "value" in resolve_root(capture.serializer.get_schema())["properties"]


def test_standalone_exclusion(serializer_factory):
    serializer = serializer_factory(
        name="handler",
        options=[OptionItem("first", int), OptionItem("second", str)],
        response_type=Parameter.empty,
    )

    assert resolve_root(serializer.get_schema(exclude=("first",))) == IsPartialDict(
        properties={"second": IsPartialDict(type="string")}
    )


def test_embed_unwraps_single_field(schema_inject, capture):
    @schema_inject
    def handler(value: int): ...

    assert capture.serializer.get_schema(embed=True) == IsPartialDict(type="integer")


def test_embed_runs_after_exclusion(schema_inject, capture):
    @schema_inject
    def handler(first: int, second: str): ...

    assert capture.serializer.get_schema(embed=True, exclude=("first",)) == IsPartialDict(
        type="string"
    )


def test_embed_unwraps_only_source_level(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input("query")]): ...

    assert resolve_root(capture.serializer.get_schema(embed=True)) == IsPartialDict(
        type="object", properties={"value": IsPartialDict(type="integer")}
    )


def test_embed_keeps_multiple_fields(schema_inject, capture):
    @schema_inject
    def handler(first: int, second: str): ...

    assert resolve_root(capture.serializer.get_schema(embed=True)) == IsPartialDict(
        properties={
            "first": IsPartialDict(type="integer"),
            "second": IsPartialDict(type="string"),
        }
    )


def test_resolve_source_reference(schema_inject, capture):
    @schema_inject
    def handler(value: Annotated[int, Input("query")]): ...

    assert capture.serializer.get_schema(resolve_refs=True)["properties"][
        "query"
    ] == IsPartialDict(properties={"value": IsPartialDict(type="integer")})


@pytest.mark.parametrize("exclude", [(1,), (("query",),), ((1, "field"),)])
def test_invalid_exclusion_fails(schema_inject, capture, exclude):
    @schema_inject
    def handler(value: int): ...

    with pytest.raises(ValueError, match="Schema exclusions"):
        capture.serializer.get_schema(exclude=exclude)
