import logging
from time import monotonic_ns
from typing import Annotated, Any

import anyio
import pytest

from fast_depends import Depends, inject
from fast_depends.exceptions import ValidationError
from fast_depends.library import CustomField
from tests.marks import serializer


class Header(CustomField):
    def use(self, /, **kwargs: Any) -> dict[str, Any]:
        kwargs = super().use(**kwargs)
        if v := kwargs.get("headers", {}).get(self.param_name):
            kwargs[self.param_name] = v
        return kwargs


class FieldHeader(Header):
    def __init__(self, *, cast: bool = True, required: bool = True) -> None:
        super().__init__(cast=cast, required=required)
        self.field = True

    def use_field(self, kwargs: Any) -> None:
        if v := kwargs.get("headers", {}).get(self.param_name):  # pragma: no branch
            kwargs[self.param_name] = v


class AsyncHeader(Header):
    async def use(self, /, **kwargs: Any) -> dict[str, Any]:
        return super().use(**kwargs)


class AsyncFieldHeader(Header):
    def __init__(self, *, cast: bool = True, required: bool = True) -> None:
        super().__init__(cast=cast, required=required)
        self.field = True

    async def use_field(self, kwargs: Any) -> None:
        await anyio.sleep(0.1)
        if v := kwargs.get("headers", {}).get(self.param_name):  # pragma: no branch
            kwargs[self.param_name] = v


def test_header():
    @inject
    def sync_catch(key: int = Header()):  # noqa: B008
        return key

    assert sync_catch(headers={"key": 1}) == 1


def test_custom_with_class():
    class T:
        @inject
        def __init__(self, key: int = Header()):
            self.key = key

    assert T(headers={"key": 1}).key == 1


def test_reusable_annotated() -> None:
    HeaderKey = Annotated[float, Header(cast=False)]

    @inject
    def sync_catch(key: HeaderKey) -> float:
        return key

    @inject
    def sync_catch2(key2: HeaderKey) -> float:
        return key2

    assert sync_catch(headers={"key": 1}) == 1
    assert sync_catch2(headers={"key2": 1}) == 1


def test_arguments_mapping():
    @inject
    def func(
        d: int = CustomField(cast=False),
        b: int = CustomField(cast=False),
        c: int = CustomField(cast=False),
        a: int = CustomField(cast=False),
    ):
        assert d == 4
        assert b == 2
        assert c == 3
        assert a == 1

    for _ in range(50):
        func(4, 2, 3, 1)


@serializer
class TestSerializer:
    @pytest.mark.anyio
    async def test_header_async(self):
        @inject
        async def async_catch(key: int = Header()):  # noqa: B008
            return key

        assert (await async_catch(headers={"key": "1"})) == 1

    def test_multiple_header(self):
        @inject
        def sync_catch(key: str = Header(), key2: int = Header()):  # noqa: B008
            assert key == "1"
            assert key2 == 2

        sync_catch(headers={"key": "1", "key2": "2"})

    @pytest.mark.anyio
    async def test_async_header_async(self):
        @inject
        async def async_catch(  # noqa: B008
            key: float = AsyncHeader(), key2: int = AsyncHeader()
        ):
            return key, key2

        assert (await async_catch(headers={"key": "1", "key2": 1})) == (1.0, 1)

    def test_sync_field_header(self):
        @inject
        def sync_catch(key: float = FieldHeader(), key2: int = FieldHeader()):  # noqa: B008
            return key, key2

        assert sync_catch(headers={"key": "1", "key2": 1}) == (1.0, 1)

    @pytest.mark.anyio
    async def test_async_field_header(self):
        @inject
        async def async_catch(  # noqa: B008
            key: float = AsyncFieldHeader(), key2: int = AsyncFieldHeader()
        ):
            return key, key2

        start = monotonic_ns()
        assert (await async_catch(headers={"key": "1", "key2": 1})) == (1.0, 1)
        assert (monotonic_ns() - start) / 10**9 < 0.2

    def test_async_header_sync(self):
        with pytest.raises(AssertionError):

            @inject
            def sync_catch(key: str = AsyncHeader()):  # pragma: no cover # noqa: B008
                return key

    def test_header_annotated(self):
        @inject
        def sync_catch(key: Annotated[int, Header()]):
            return key

        assert sync_catch(headers={"key": 1}) == 1

    def test_header_required(self):
        @inject
        def sync_catch(key=Header()):  # pragma: no cover # noqa: B008
            return key

        with pytest.raises(ValidationError):
            sync_catch()

    def test_header_not_required(self):
        @inject
        def sync_catch(key2=Header(required=False)):  # noqa: B008
            assert key2 is None

        sync_catch()

    def test_header_not_required_with_default(self):
        @inject
        def sync_catch(key2: Annotated[str, Header(required=False)] = "1"):  # noqa: B008
            return key2 == "1"

        assert sync_catch()

    def test_depends(self):
        def dep(key: Annotated[int, Header()]):
            return key

        @inject
        def sync_catch(k=Depends(dep)):
            return k

        assert sync_catch(headers={"key": 1}) == 1

    def test_not_cast(self):
        @inject
        def sync_catch(key: Annotated[float, Header(cast=False)]):
            return key

        assert sync_catch(headers={"key": 1}) == 1

        @inject
        def sync_catch(key: logging.Logger = Header(cast=False)):  # noqa: B008
            return key

        assert sync_catch(headers={"key": 1}) == 1
