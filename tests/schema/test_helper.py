from typing import Annotated, Any

import pytest
from dirty_equals import IsPartialDict

from fast_depends import Depends
from fast_depends.core import build_call_model
from fast_depends.schema import get_schema
from tests.library.test_serializer import EchoSerializerFactory
from tests.schema.custom_fields import Input, source_schema
from tests.serializers.test_schema import resolve_root


@pytest.mark.parametrize("embed", (False, True))
@pytest.mark.parametrize("resolve_refs", (False, True))
def test_helper_uses_bound_backend_and_processing(
    schema_inject, capture, embed, resolve_refs
):
    @schema_inject
    def handler(token: Annotated[str, Input("headers")], secret: str): ...

    # An iterable can contain both root and source-field exclusions.
    exclude = (item for item in ("secret", ("headers", "missing")))
    schema = get_schema(
        capture.model, embed=embed, resolve_refs=resolve_refs, exclude=exclude
    )
    assert schema == capture.serializer.get_schema(
        embed=embed, resolve_refs=resolve_refs, exclude=("secret", ("headers", "missing"))
    )
    fields = resolve_root(schema) if embed else source_schema(schema, "headers")
    assert fields == IsPartialDict(properties={"token": IsPartialDict(type="string")})


def test_helper_uses_live_dependency_overrides(schema_inject, capture, provider):
    def original(old: int): ...
    def replacement(new: str): ...

    @schema_inject
    def handler(value: Any = Depends(original)): ...

    assert resolve_root(get_schema(capture.model)) == IsPartialDict(
        properties={"old": IsPartialDict(type="integer")}
    )
    with provider.scope(original, replacement):
        assert resolve_root(get_schema(capture.model)) == IsPartialDict(
            properties={"new": IsPartialDict(type="string")}
        )
    assert resolve_root(get_schema(capture.model)) == IsPartialDict(
        properties={"old": IsPartialDict(type="integer")}
    )


def test_helper_empty_inputs_are_an_object(schema_inject, capture):
    @schema_inject
    def handler(): ...

    assert resolve_root(get_schema(capture.model)) == IsPartialDict(
        type="object", properties={}
    )


def test_helper_excluding_all_inputs_keeps_object(schema_inject, capture):
    @schema_inject
    def handler(value: int): ...

    assert resolve_root(
        get_schema(capture.model, exclude=("value",), embed=True)
    ) == IsPartialDict(type="object", properties={})


def test_helper_rejects_absent_serializer(provider):
    def handler(value: int): ...

    call = build_call_model(handler, dependency_provider=provider)
    with pytest.raises(ValueError, match="configured serializer"):
        get_schema(call)


def test_helper_preserves_unsupported_custom_serializer_error(provider):
    def handler(value: int): ...

    call = build_call_model(
        handler, dependency_provider=provider, serializer_cls=EchoSerializerFactory()
    )
    with pytest.raises(NotImplementedError):
        get_schema(call)
