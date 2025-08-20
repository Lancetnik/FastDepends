import pytest

from fast_depends import Provider


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def provider() -> Provider:
    return Provider()
