from typing import Any
from unittest.mock import Mock

import pytest

from fast_depends import Depends, inject


def test_schema_preserves_argument_casting(schema_inject, capture):
    def dependency(count: int):
        return count + 1

    @schema_inject
    def handler(value: int = Depends(dependency)):
        return value * 2

    capture.serializer.get_schema()

    assert handler(count="2") == 6


def test_schema_preserves_response_casting(schema_inject, capture):
    @schema_inject
    def handler() -> int:
        return "2"

    capture.serializer.get_schema()

    assert handler() == 2


@pytest.mark.anyio
async def test_schema_preserves_async_dependency_casting(schema_inject, capture):
    async def dependency(count: int):
        return count + 1

    @schema_inject
    async def handler(value: int = Depends(dependency)):
        return value * 2

    capture.serializer.get_schema()

    assert await handler(count="2") == 6


def test_schema_preserves_response_schema(schema_inject, capture):
    def dependency(count: int): ...

    @schema_inject
    def handler(value: Any = Depends(dependency)) -> list[int]: ...

    serializer = capture.serializer
    response = serializer.get_response_schema()

    serializer.get_schema()

    assert serializer.get_response_schema() == response


def test_schema_keeps_bound_serializer(schema_inject, capture):
    @schema_inject
    def handler(count: int): ...

    serializer = capture.serializer

    serializer.get_schema()

    assert capture.serializer is serializer


def test_schema_does_not_create_another_serializer(serializer_factory, capture, provider):
    factory = Mock(wraps=serializer_factory)

    def dependency(count: int): ...

    @inject(serializer_cls=factory, dependency_provider=provider, wrap_model=capture)
    def handler(value: Any = Depends(dependency)): ...

    factory.reset_mock()

    capture.serializer.get_schema()
    capture.serializer.get_schema()

    factory.assert_not_called()


def test_cast_false_keeps_serializer_absent(schema_inject, capture):
    @schema_inject(cast=False)
    def handler(count: int): ...

    assert capture.model.serializer is None


def test_explicitly_absent_serializer(capture, provider):
    @inject(serializer_cls=None, dependency_provider=provider, wrap_model=capture)
    def handler(count: int): ...

    assert capture.model.serializer is None
