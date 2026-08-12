import pytest

from fast_depends.exceptions import ValidationError
from fast_depends.library.serializer import OptionItem

EXPECTED = {"a": OptionItem(field_name="a", field_type=int)}


def test_str_with_keyword_options() -> None:
    error = ValidationError(
        incoming_options={"a": "not-an-int"},
        locations=("a",),
        expected=EXPECTED,
        original_error=ValueError("original"),
    )

    assert str(error) == (
        "\n    Incoming options: a=`not-an-int`"
        "\n    In the following option types error occurred:"
        "\n    OptionItem[a, type=`int`]"
    )


def test_str_with_positional_options() -> None:
    error = ValidationError(
        incoming_options="not-an-int",
        locations=("a",),
        expected=EXPECTED,
        original_error=ValueError("original"),
    )

    assert str(error) == (
        "\n    Incoming options: `not-an-int`"
        "\n    In the following option types error occurred:"
        "\n    OptionItem[a, type=`int`]"
    )


def test_unknown_location_falls_back_to_all_expected_options() -> None:
    error = ValidationError(
        incoming_options={"a": "not-an-int"},
        locations=("unknown",),
        expected=EXPECTED,
        original_error=ValueError("original"),
    )

    assert error.error_fields == tuple(EXPECTED.values())


def test_is_a_value_error() -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        raise ValidationError(
            incoming_options={},
            locations=(),
            expected={},
            original_error=ValueError("original"),
        )
