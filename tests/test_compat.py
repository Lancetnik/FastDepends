import sys
import types
import typing
from types import NoneType

import pytest

from fast_depends._compat import (
    eval_type_backport,
    evaluate_forwardref,
    is_backport_fixable_error,
)

# `X | Y` and `X[Y]` are valid syntax on every supported Python version, so a
# backport-fixable `TypeError` can only be provoked with a non-type operand.
NOT_A_TYPE = object()
BACKPORT_NS = {"NOT_A_TYPE": NOT_A_TYPE, "typing": typing}


def forwardref(annotation: str) -> typing.ForwardRef:
    return typing.ForwardRef(annotation, is_argument=False, is_class=True)


def test_evaluate_forwardref_none() -> None:
    assert evaluate_forwardref(None) is NoneType


def test_evaluate_forwardref_string() -> None:
    assert evaluate_forwardref("int", {"int": int}, {}) is int


def test_evaluate_forwardref_tolerates_unresolvable_name() -> None:
    # The whole point of the helper: an unresolvable reference is returned as is
    # instead of raising `NameError`.
    resolved = evaluate_forwardref("Undefined", {}, {})
    assert isinstance(resolved, typing.ForwardRef)
    assert resolved.__forward_arg__ == "Undefined"


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        pytest.param(
            "unsupported operand type(s) for |: 'object' and 'NoneType'",
            True,
            id="union-syntax",
        ),
        pytest.param(
            "'object' object is not subscriptable",
            True,
            id="subscription-syntax",
        ),
        pytest.param("some other problem", False, id="unrelated"),
    ),
)
def test_is_backport_fixable_error(message: str, expected: bool) -> None:
    assert is_backport_fixable_error(TypeError(message)) is expected


def test_eval_type_backport_reraises_unrelated_type_error() -> None:
    with pytest.raises(TypeError, match="requires a single type"):
        eval_type_backport(forwardref("typing.Optional[int, str]"), BACKPORT_NS, {})


@pytest.mark.parametrize(
    "annotation",
    (
        pytest.param("NOT_A_TYPE | None", id="union-syntax"),
        pytest.param("NOT_A_TYPE[int]", id="subscription-syntax"),
    ),
)
def test_eval_type_backport_without_package_installed(
    annotation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A `None` entry in `sys.modules` makes the import fail deterministically,
    # whether or not `eval_type_backport` is actually installed.
    monkeypatch.setitem(sys.modules, "eval_type_backport", None)

    with pytest.raises(TypeError, match="install the `eval_type_backport` package"):
        eval_type_backport(forwardref(annotation), BACKPORT_NS, {})


def test_eval_type_backport_delegates_to_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_backport(
        value: typing.Any,
        globalns: typing.Any,
        localns: typing.Any,
        try_default: bool,
    ) -> str:
        calls.append(try_default)
        return "delegated"

    stub = types.ModuleType("eval_type_backport")
    stub.eval_type_backport = fake_backport  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "eval_type_backport", stub)

    assert eval_type_backport(forwardref("NOT_A_TYPE | None"), BACKPORT_NS, {}) == (
        "delegated"
    )
    assert calls == [False]
