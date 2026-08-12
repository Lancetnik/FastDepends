import msgspec
import pytest

from fast_depends import Depends, Provider, inject
from fast_depends.exceptions import ValidationError
from fast_depends.msgspec import MsgSpecSerializer


class TestNativeErrors:
    """`use_fastdepends_errors=False` keeps the original `msgspec` errors."""

    serializer = MsgSpecSerializer(use_fastdepends_errors=False)

    def test_arguments_are_casted(self) -> None:
        @inject(serializer_cls=self.serializer, dependency_provider=Provider())
        def func(a: int, b: float):
            return a, b

        assert func("1", b="2.5") == (1, 2.5)

    def test_response_is_casted(self) -> None:
        @inject(
            serializer_cls=self.serializer,
            dependency_provider=Provider(),
            cast_result=True,
        )
        def func(a: int) -> float:
            return a

        result = func("1")
        assert isinstance(result, float)
        assert result == 1.0

    def test_argument_error_is_not_wrapped(self) -> None:
        @inject(serializer_cls=self.serializer, dependency_provider=Provider())
        def func(a: int):
            raise AssertionError("unreachable")

        with pytest.raises(msgspec.ValidationError):
            func("not-an-int")

    def test_response_error_is_not_wrapped(self) -> None:
        @inject(
            serializer_cls=self.serializer,
            dependency_provider=Provider(),
            cast_result=True,
        )
        def func() -> int:
            return "not-an-int"

        with pytest.raises(msgspec.ValidationError):
            func()


class TestFastDependsErrors:
    """`use_fastdepends_errors=True` (the default) wraps them instead."""

    serializer = MsgSpecSerializer(use_fastdepends_errors=True)

    def test_argument_error_is_wrapped(self) -> None:
        @inject(serializer_cls=self.serializer, dependency_provider=Provider())
        def func(a: int):
            raise AssertionError("unreachable")

        with pytest.raises(ValidationError):
            func("not-an-int")

    def test_response_error_is_wrapped(self) -> None:
        @inject(
            serializer_cls=self.serializer,
            dependency_provider=Provider(),
            cast_result=True,
        )
        def func() -> int:
            return "not-an-int"

        with pytest.raises(ValidationError):
            func()


@pytest.mark.parametrize(
    "serializer",
    (
        pytest.param(MsgSpecSerializer(use_fastdepends_errors=True), id="wrapped"),
        pytest.param(MsgSpecSerializer(use_fastdepends_errors=False), id="native"),
    ),
)
def test_field_alias(serializer: MsgSpecSerializer) -> None:
    def dep(nested: int = msgspec.field(name="nestedAlias")) -> int:
        return nested

    @inject(serializer_cls=serializer, dependency_provider=Provider())
    def func(
        a: int = msgspec.field(name="aliasedA"),
        d: int = Depends(dep),
    ) -> tuple[int, int]:
        return a, d

    assert func(aliasedA="1", nestedAlias="2") == (1, 2)
