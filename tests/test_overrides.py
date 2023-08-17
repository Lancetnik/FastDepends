from unittest.mock import Mock

import pytest

from fast_depends import Depends, dependency_provider, inject, Provider


@pytest.fixture
def provider():
    yield dependency_provider
    dependency_provider.clear()


def test_not_override(provider):
    mock = Mock()

    def base_dep():  # pragma: no cover
        mock.original()
        return 1

    @inject(dependency_overrides_provider=None)
    def func(d=Depends(base_dep)):
        assert d == 1

    func()

    mock.original.assert_called_once()


def test_sync_override(provider):
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


def test_sync_override_custom_provider(provider: Provider):
    custom_provider = Provider()
    mock = Mock()

    def base_dep():  # pragma: no cover
        mock.original()
        return 1

    def override_dep():
        mock.override()
        return 2

    custom_provider.override(base_dep, override_dep)

    def func(d=Depends(base_dep)):
        assert d == 2

    func = inject(func, dependency_overrides_provider=custom_provider)
    func()

    mock.override.assert_called_once()
    assert not mock.original.called
    assert not provider.dependency_overrides


def test_sync_not_override_custom_provider(provider: Provider):
    custom_provider = Provider()
    mock = Mock()

    def base_dep():  # pragma: no cover
        mock.original()
        return 1

    def func(d=Depends(base_dep)):
        assert d == 1

    func = inject(func, dependency_overrides_provider=custom_provider)
    func()

    mock.original.assert_called_once()


def test_sync_by_async_override(provider):
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
async def test_async_override(provider):
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
async def test_async_override_custom_provider(provider: Provider):
    custom_provider = Provider()
    mock = Mock()

    async def base_dep():  # pragma: no cover
        mock.original()
        return 1

    async def override_dep():
        mock.override()
        return 2

    custom_provider.override(base_dep, override_dep)

    async def func(d=Depends(base_dep)):
        assert d == 2

    func = inject(func, dependency_overrides_provider=custom_provider)
    await func()

    mock.override.assert_called_once()
    assert not mock.original.called
    assert not provider.dependency_overrides


@pytest.mark.asyncio
async def test_not_async_override_custom_provider(provider: Provider):
    custom_provider = Provider()
    mock = Mock()

    async def base_dep():  # pragma: no cover
        mock.original()
        return 1

    async def func(d=Depends(base_dep)):
        assert d == 1

    func = inject(func, dependency_overrides_provider=custom_provider)
    await func()

    mock.original.assert_called_once()


@pytest.mark.asyncio
async def test_async_by_sync_override(provider):
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
