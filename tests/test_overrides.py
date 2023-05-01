from unittest.mock import Mock

import pytest

from fast_depends import Depends, dependency_provider, inject


@pytest.fixture
def provider():
    yield dependency_provider
    dependency_provider.clear()


def test_sync_overide(provider):
    mock = Mock()

    def base_dep():  # pragma: no cover
        mock.original()
        return 1

    def override_dep():
        mock.override()
        return 2

    provider.override(base_dep, override_dep)

    @inject
    def func(d=Depends(base_dep)):
        assert d == 2

    func()

    mock.override.assert_called_once()
    assert not mock.original.called


def test_sync_by_async_overide(provider):
    def base_dep():  # pragma: no cover
        return 1

    async def override_dep():  # pragma: no cover
        return 2

    provider.override(base_dep, override_dep)

    @inject
    def func(d=Depends(base_dep)):
        pass

    with pytest.raises(AssertionError):
        func()


@pytest.mark.asyncio
async def test_async_overide(provider):
    mock = Mock()

    async def base_dep():  # pragma: no cover
        mock.original()
        return 1

    async def override_dep():
        mock.override()
        return 2

    provider.override(base_dep, override_dep)

    @inject
    async def func(d=Depends(base_dep)):
        assert d == 2

    await func()

    mock.override.assert_called_once()
    assert not mock.original.called


@pytest.mark.asyncio
async def test_async_by_sync_overide(provider):
    mock = Mock()

    async def base_dep():  # pragma: no cover
        mock.original()
        return 1

    def override_dep():
        mock.override()
        return 2

    provider.override(base_dep, override_dep)

    @inject
    async def func(d=Depends(base_dep)):
        assert d == 2

    await func()

    mock.override.assert_called_once()
    assert not mock.original.called
