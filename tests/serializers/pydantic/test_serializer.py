from datetime import date

import pytest

from fast_depends import Provider, inject
from fast_depends.core import build_call_model
from fast_depends.exceptions import ValidationError
from fast_depends.pydantic import PydanticSerializer


def test_non_class_response_type() -> None:
    """`issubclass()` raises for non-class annotations such as unions.

    The serializer has to fall back to a `TypeAdapter` instead of treating the
    annotation as a model.
    """

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=Provider(),
        cast_result=True,
    )
    def func(a: int) -> int | None:
        return a

    assert func("1") == 1


def test_json_call_preserves_strict_python_validation(provider: Provider) -> None:
    def handler(value: date) -> date:
        return value

    invoke = build_call_model(
        handler,
        dependency_provider=provider,
        serializer_cls=PydanticSerializer({"strict": True}),
    ).prepare_json_call(embed=True)
    assert invoke is not None
    with pytest.raises(ValidationError):
        invoke(b'"2026-11-16"')
    value = date(2026, 11, 16)
    assert invoke(b'"2026-11-16"', load_arguments=lambda: ((value,), {})) == value
