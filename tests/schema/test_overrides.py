from typing import Any

from dirty_equals import IsPartialDict

from fast_depends import Depends
from tests.serializers.test_schema import resolve_root


def test_override_after_schema_generation(schema_inject, capture, provider):
    def original(old: int): ...

    def replacement(new: str): ...

    @schema_inject
    def handler(value: Any = Depends(original)): ...

    serializer = capture.serializer
    serializer.get_schema()
    provider.override(original, replacement)

    assert resolve_root(serializer.get_schema()) == IsPartialDict(
        properties={"new": IsPartialDict(type="string")}
    )


def test_override_before_decoration(schema_inject, capture, provider):
    def original(old: int): ...

    def replacement(new: str): ...

    provider.override(original, replacement)

    @schema_inject
    def handler(value: Any = Depends(original)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"new": IsPartialDict(type="string")}
    )


def test_override_nested_inputs(schema_inject, capture, provider):
    def original(old: int): ...

    def nested(token: str): ...

    def replacement(value: Any = Depends(nested)): ...

    @schema_inject
    def handler(value: Any = Depends(original)): ...

    provider.override(original, replacement)

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"token": IsPartialDict(type="string")}
    )


def test_extra_dependency_override(schema_inject, capture, provider):
    def original(old: int): ...

    def replacement(new: str): ...

    @schema_inject(extra_dependencies=(Depends(original),))
    def handler(): ...

    provider.override(original, replacement)

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"new": IsPartialDict(type="string")}
    )


def test_extra_dependency_override_before_decoration(schema_inject, capture, provider):
    def original(old: int): ...

    def replacement(new: str): ...

    provider.override(original, replacement)

    @schema_inject(extra_dependencies=(Depends(original),))
    def handler(): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"new": IsPartialDict(type="string")}
    )


def test_schema_in_provider_scope(schema_inject, capture, provider):
    def original(old: int): ...

    def replacement(new: str): ...

    @schema_inject
    def handler(value: Any = Depends(original)): ...

    with provider.scope(original, replacement):
        assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
            properties={"new": IsPartialDict(type="string")}
        )


def test_schema_after_provider_scope(schema_inject, capture, provider):
    def original(old: int): ...

    def replacement(new: str): ...

    @schema_inject
    def handler(value: Any = Depends(original)): ...

    with provider.scope(original, replacement):
        capture.serializer.get_schema()

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"old": IsPartialDict(type="integer")}
    )
