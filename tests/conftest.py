import pytest

from fast_depends.dependencies.provider import Provider


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def provider() -> Provider:
    return Provider()
