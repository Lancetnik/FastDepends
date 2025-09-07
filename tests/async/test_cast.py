from collections.abc import Iterator

import pytest

from fast_depends import inject
from fast_depends.exceptions import ValidationError
from tests.marks import serializer


@pytest.mark.anyio
async def test_skip_not_required() -> None:
    @inject(serializer_cls=None)
    async def some_func() -> int:
        return 1

    assert await some_func(useless=object()) == 1


@pytest.mark.anyio
async def test_not_annotated() -> None:
    @inject
    async def some_func(a, b):
        return a + b

    assert isinstance(await some_func("1", "2"), str)


@pytest.mark.anyio
async def test_arbitrary_args() -> None:
    class ArbitraryType:
        def __init__(self):
            self.value = "value"

    @inject
    async def some_func(a: ArbitraryType):
        return a

    assert isinstance(await some_func(ArbitraryType()), ArbitraryType)


@pytest.mark.anyio
async def test_arbitrary_response() -> None:
    class ArbitraryType:
        def __init__(self):
            self.value = "value"

    @inject
    async def some_func(a: ArbitraryType) -> ArbitraryType:
        return a

    assert isinstance(await some_func(ArbitraryType()), ArbitraryType)


@pytest.mark.anyio
async def test_args() -> None:
    @inject
    async def some_func(a, *ar):
        return a, ar

    assert (1, (2,)) == await some_func(1, 2)


@pytest.mark.anyio
async def test_args_kwargs_1() -> None:
    @inject
    async def simple_func(
        a: int,
        *args: tuple[float, ...],
        b: int,
        **kwargs: dict[str, int],
    ):
        return a, args, b, kwargs

    assert (1, (2.0, 3.0), 3, {"key": 1}) == await simple_func(
        1.0, 2.0, 3, b=3.0, key=1.0
    )


@pytest.mark.anyio
async def test_args_kwargs_2() -> None:
    @inject
    async def simple_func(
        a: int,
        *args: tuple[float, ...],
        b: int,
    ):
        return a, args, b

    assert (1, (2.0, 3.0), 3) == await simple_func(
        1.0,
        2.0,
        3,
        b=3.0,
    )


@pytest.mark.anyio
async def test_args_kwargs_3() -> None:
    @inject
    async def simple_func(a: int, *, b: int):
        return a, b

    assert (1, 3) == await simple_func(
        1.0,
        b=3.0,
    )


@pytest.mark.anyio
async def test_args_kwargs_4() -> None:
    @inject
    async def simple_func(
        *args: tuple[float, ...],
        **kwargs: dict[str, int],
    ):
        return args, kwargs

    assert (
        (1.0, 2.0, 3.0),
        {
            "key": 1,
            "b": 3,
        },
    ) == await simple_func(1.0, 2.0, 3, b=3.0, key=1.0)


@pytest.mark.anyio
async def test_args_kwargs_5() -> None:
    @inject
    async def simple_func(
        *a: tuple[float, ...],
        **kw: dict[str, int],
    ):
        return a, kw

    assert (
        (1.0, 2.0, 3.0),
        {
            "key": 1,
            "b": 3,
        },
    ) == await simple_func(1.0, 2.0, 3, b=3.0, key=1.0)


@serializer
@pytest.mark.anyio
class TestSerialization:
    async def test_no_cast_result(self) -> None:
        @inject(cast_result=False)
        async def some_func(a: int, b: int) -> str:
            return a + b

        assert await some_func("1", "2") == 3

    async def test_annotated_partial(self) -> None:
        @inject
        async def some_func(a, b: int):
            assert isinstance(b, int)
            return a + b

        assert isinstance(await some_func(1, "2"), int)

    async def test_types_casting(self) -> None:
        @inject
        async def some_func(a: int, b: int) -> float:
            assert isinstance(a, int)
            assert isinstance(b, int)
            r = a + b
            assert isinstance(r, int)
            return r

        assert isinstance(await some_func("1", "2"), float)

    async def test_types_casting_from_str(self) -> None:
        @inject
        async def some_func(a: "int") -> float:
            return a

        assert isinstance(await some_func("1"), float)

    async def test_wrong_incoming_types(self) -> None:
        @inject
        async def some_func(a: int):  # pragma: no cover
            return a

        with pytest.raises(ValidationError):
            await some_func({"key", 1})

    async def test_wrong_return_types(self) -> None:
        @inject
        async def some_func(a: int) -> dict:
            return a

        with pytest.raises(ValidationError):
            await some_func("2")

    async def test_generator(self) -> None:
        @inject
        async def simple_func(a: str) -> int:
            for _ in range(2):
                yield a

        async for i in simple_func("1"):
            assert i == 1

    async def test_generator_iterator_type(self) -> None:
        @inject
        async def simple_func(a: str) -> Iterator[int]:
            for _ in range(2):
                yield a

        async for i in simple_func("1"):
            assert i == 1
