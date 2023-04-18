from typing_extensions import Annotated
import logging

import pytest

from fast_depends.library import CustomField
from fast_depends.types import AnyDict
from fast_depends import inject, Depends


class Header(CustomField):
    def use(self, **kwargs: AnyDict) -> AnyDict:
        kwargs = super().use(**kwargs)
        kwargs[self.param_name] = kwargs["headers"][self.param_name]
        return kwargs


class AsyncHeader(Header):
    async def use(self, **kwargs: AnyDict) -> AnyDict:
        return super().use(**kwargs)


def test_header():
    @inject
    def catch(key: str = Header()):
        return key

    assert catch(headers={"key": 1}) == "1"


@pytest.mark.asyncio
async def test_header_async():
    @inject
    async def catch(key: str = Header()):
        return key

    assert (await catch(headers={"key": 1})) == "1"


@pytest.mark.asyncio
async def test_adync_header_async():
    @inject
    async def catch(key: str = AsyncHeader()):
        return key

    assert (await catch(headers={"key": 1})) == "1"


def test_adync_header_sync():
    @inject
    def catch(key: str = AsyncHeader()):  # pragma: no cover
        return key

    with pytest.raises(AssertionError):
        catch(headers={"key": 1}) == "1"


def test_header_annotated():
    @inject
    def catch(key: Annotated[str, Header()]):
        return key

    assert catch(headers={"key": 1}) == "1"


def test_depends():
    def dep(key: Annotated[str, Header()]):
        return key

    @inject
    def catch(k = Depends(dep)):
        return k

    assert catch(headers={"key": 1}) == "1"


def test_not_cast():
    @inject
    def catch(key: Annotated[str, Header(cast=False)]):
        return key

    assert catch(headers={"key": 1}) == 1

    @inject
    def catch(key: logging.Logger = Header(cast=False)):
        return key

    assert catch(headers={"key": 1}) == 1
