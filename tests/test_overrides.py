from collections.abc import Generator
from unittest.mock import Mock

import pytest

from fast_depends import Depends, Provider, inject


def test_not_override(provider: Provider) -> None:
    mock = Mock()

    def base_dep():  # pragma: no cover
        mock.original()
        return 1

    @inject(dependency_provider=provider)
    def func(d=Depends(base_dep)):
        assert d == 1

    func()

    mock.original.assert_called_once()


def test_sync_override(provider: Provider) -> None:
    mock = Mock()

    def base_dep():  # pragma: no cover
        mock.original()
        return 1

    def override_dep():
        mock.override()
        return 2

    provider.override(base_dep, override_dep)

    @inject(dependency_provider=provider)
    def func(d=Depends(base_dep)):
        assert d == 2

    func()

    mock.override.assert_called_once()
    assert not mock.original.called


def test_override_context(provider: Provider) -> None:
    def base_dep():
        return 1

    def override_dep():
        return 2

    @inject(dependency_provider=provider)
    def func(d=Depends(base_dep)):
        return d

    with provider.scope(base_dep, override_dep):
        assert func() == 2

    assert func() == 1


def test_sync_by_async_override(provider: Provider) -> None:
    def base_dep():  # pragma: no cover
        return 1

    async def override_dep():  # pragma: no cover
        return 2

    provider.override(base_dep, override_dep)

    with pytest.raises(AssertionError):

        @inject(dependency_provider=provider)
        def func(d=Depends(base_dep)):
            pass


def test_sync_by_async_override_in_extra(provider: Provider) -> None:
    def base_dep():  # pragma: no cover
        return 1

    async def override_dep():  # pragma: no cover
        return 2

    provider.override(base_dep, override_dep)

    with pytest.raises(AssertionError):

        @inject(
            dependency_provider=provider,
            extra_dependencies=(Depends(base_dep),),
        )
        def func():
            pass


@pytest.mark.anyio
async def test_async_override(provider: Provider) -> None:
    mock = Mock()

    async def base_dep():  # pragma: no cover
        mock.original()
        return 1

    async def override_dep():
        mock.override()
        return 2

    provider.override(base_dep, override_dep)

    @inject(dependency_provider=provider)
    async def func(d=Depends(base_dep)):
        assert d == 2

    await func()

    mock.override.assert_called_once()
    assert not mock.original.called


@pytest.mark.anyio
async def test_async_by_sync_override(provider: Provider) -> None:
    mock = Mock()

    async def base_dep():  # pragma: no cover
        mock.original()
        return 1

    def override_dep():
        mock.override()
        return 2

    provider.override(base_dep, override_dep)

    @inject(dependency_provider=provider)
    async def func(d=Depends(base_dep)):
        assert d == 2

    await func()

    mock.override.assert_called_once()
    assert not mock.original.called


def test_deep_overrides(provider: Provider) -> None:
    mock = Mock()

    def dep1(c=Depends(mock.dep2)):
        mock.dep1()

    def dep3(c=Depends(mock.dep4)):
        mock.dep3()

    @inject(
        dependency_provider=provider,
        extra_dependencies=(Depends(dep1),),
    )
    def func():
        return

    func()
    mock.dep1.assert_called_once()
    mock.dep2.assert_called_once()
    assert not mock.dep3.called
    assert not mock.dep4.called
    mock.reset_mock()

    with provider.scope(dep1, dep3):
        func()
        assert not mock.dep1.called
        assert not mock.dep2.called
        mock.dep3.assert_called_once()
        mock.dep4.assert_called_once()


def test_deep_overrides_with_different_signatures(provider: Provider) -> None:
    mock = Mock()

    def dep1(c=Depends(mock.dep2)):
        mock.dep1()

    def dep3():
        mock.dep3()

    @inject(
        dependency_provider=provider,
        extra_dependencies=(Depends(dep1),),
    )
    def func():
        return

    func()
    mock.dep1.assert_called_once()
    mock.dep2.assert_called_once()
    assert not mock.dep3.called
    mock.reset_mock()

    with provider.scope(dep1, dep3):
        func()
        assert not mock.dep1.called
        assert not mock.dep2.called
        mock.dep3.assert_called_once()


def test_override_context_with_generator(provider: Provider) -> None:
    def base_dep() -> Generator[int, None, None]:
        yield 1

    def override_dep() -> Generator[int, None, None]:
        yield 2

    @inject(dependency_provider=provider)
    def func(d=Depends(base_dep)):
        return d

    with provider.scope(base_dep, override_dep):
        assert func() == 2


def test_override_context_with_undefined_generator(provider: Provider) -> None:
    def base_dep() -> Generator[int, None, None]:
        raise NotImplementedError

    def override_dep() -> Generator[int, None, None]:
        yield 2

    @inject(dependency_provider=provider)
    def func(d=Depends(base_dep)):
        return d

    with provider.scope(base_dep, override_dep):
        assert func() == 2


@pytest.mark.anyio
async def test_async_override_context_with_generator(provider: Provider) -> None:
    async def base_dep() -> Generator[int, None, None]:
        yield 1

    async def override_dep() -> Generator[int, None, None]:
        yield 2

    @inject(dependency_provider=provider)
    async def func(d=Depends(base_dep)):
        return d

    with provider.scope(base_dep, override_dep):
        assert await func() == 2


@pytest.mark.anyio
async def test_async_override_context_with_undefined_generator(
    provider: Provider,
) -> None:
    async def base_dep() -> Generator[int, None, None]:
        raise NotImplementedError

    async def override_dep() -> Generator[int, None, None]:
        yield 2

    @inject(dependency_provider=provider)
    async def func(d=Depends(base_dep)):
        return d

    with provider.scope(base_dep, override_dep):
        assert await func() == 2
