import logging
from typing import Any, Callable

import pydantic
import pytest
from typing_extensions import Annotated

from fast_depends import Depends, inject
from fast_depends.library import CustomField


class Header(CustomField):
    def use(self, **kwargs: Callable[..., Any]) -> Callable[..., Any]:
        kwargs = super().use(**kwargs)
        if kwargs.get("headers", {}).get(self.param_name):
            kwargs[self.param_name] = kwargs.get("headers", {}).get(self.param_name)
        return kwargs


class AsyncHeader(Header):
    async def use(self, **kwargs: Callable[..., Any]) -> Callable[..., Any]:
        return super().use(**kwargs)


def test_header():
    @inject
    def sync_catch(key: int = Header()):  # noqa: B008
        return key

    assert sync_catch(headers={"key": "1"}) == 1


@pytest.mark.asyncio
async def test_header_async():
    @inject
    async def async_catch(key: int = Header()):  # noqa: B008
        return key

    assert (await async_catch(headers={"key": "1"})) == 1


def test_multiple_header():
    @inject
    def sync_catch(key: str = Header(), key2: int = Header()):  # noqa: B008
        assert key == "1"
        assert key2 == 2

    sync_catch(headers={"key": "1", "key2": "2"})


@pytest.mark.asyncio
async def test_async_header_async():
    @inject
    async def async_catch(key: float = AsyncHeader()):  # noqa: B008
        return key

    assert (await async_catch(headers={"key": "1"})) == 1.0


def test_async_header_sync():
    with pytest.raises(AssertionError):

        @inject
        def sync_catch(key: str = AsyncHeader()):  # pragma: no cover # noqa: B008
            return key


def test_header_annotated():
    @inject
    def sync_catch(key: Annotated[int, Header()]):
        return key

    assert sync_catch(headers={"key": "1"}) == 1


def test_header_required():
    @inject
    def sync_catch(key2=Header()):  # pragma: no cover # noqa: B008
        return key2

    with pytest.raises(pydantic.ValidationError):
        sync_catch()


def test_header_not_required():
    @inject
    def sync_catch(key2=Header(required=False)):  # noqa: B008
        assert key2 is None

    sync_catch()


def test_depends():
    def dep(key: Annotated[int, Header()]):
        return key

    @inject
    def sync_catch(k=Depends(dep)):
        return k

    assert sync_catch(headers={"key": "1"}) == 1


def test_not_cast():
    @inject
    def sync_catch(key: Annotated[float, Header(cast=False)]):
        return key

    assert sync_catch(headers={"key": 1}) == 1

    @inject
    def sync_catch(key: logging.Logger = Header(cast=False)):  # noqa: B008
        return key

    assert sync_catch(headers={"key": 1}) == 1
