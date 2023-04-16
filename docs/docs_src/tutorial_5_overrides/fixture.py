from unittest.mock import Mock

import pytest
from fast_depends import dependency_provider, inject, Depends


@pytest.fixture
def provider():
    yield dependency_provider
    dependency_provider.clear() # (1)!

def test_sync_overide(provider):
    mock = Mock()

    def base_dep():
        mock.original()
        return 1

    def override_dep():
        mock.override()
        return 2

    provider.override(base_dep, override_dep)

    @inject
    def func(d = Depends(base_dep)):
        assert d == 2

    func()

    mock.override.assert_called_once()
    assert not mock.original.called