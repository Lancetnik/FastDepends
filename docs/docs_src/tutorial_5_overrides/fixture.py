import pytest

from fast_depends import Depends, dependency_provider, inject

# Base code

def base_dep():
    return 1

def override_dep():
    return 2

@inject
def func(d = Depends(base_dep)):
    return d

# Tests

@pytest.fixture
def provider():
    yield dependency_provider
    dependency_provider.clear() # (1)!

def test_sync_overide(provider):
    provider.override(base_dep, override_dep)
    assert func() == 2
