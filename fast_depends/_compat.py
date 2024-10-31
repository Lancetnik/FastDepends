import sys
import typing
from importlib.metadata import version as get_version

__all__ = (
    "ExceptionGroup",
    "evaluate_forwardref",
)


ANYIO_V3 = get_version("anyio").startswith("3.")

if ANYIO_V3:
    from anyio import ExceptionGroup as ExceptionGroup
else:
    if sys.version_info < (3, 11):
        from exceptiongroup import ExceptionGroup as ExceptionGroup
    else:
        ExceptionGroup = ExceptionGroup


def evaluate_forwardref(
    value: typing.Any,
    globalns: typing.Optional[dict[str, typing.Any]] = None,
    localns: typing.Optional[dict[str, typing.Any]] = None,
) -> typing.Any:
    """Behaves like typing._eval_type, except it won't raise an error if a forward reference can't be resolved."""
    if value is None:
        value = NoneType
    elif isinstance(value, str):
        value = _make_forward_ref(value, is_argument=False, is_class=True)

    try:
        return eval_type_backport(value, globalns, localns)
    except NameError:
        # the point of this function is to be tolerant to this case
        return value


def eval_type_backport(
    value: typing.Any,
    globalns: typing.Optional[dict[str, typing.Any]] = None,
    localns: typing.Optional[dict[str, typing.Any]] = None,
) -> typing.Any:
    """Like `typing._eval_type`, but falls back to the `eval_type_backport` package if it's
    installed to let older Python versions use newer typing features.
    Specifically, this transforms `X | Y` into `typing.Union[X, Y]`
    and `list[X]` into `typing.List[X]` etc. (for all the types made generic in PEP 585)
    if the original syntax is not supported in the current Python version.
    """
    try:
        return typing._eval_type(  # type: ignore
            value, globalns, localns
        )
    except TypeError as e:
        if not (isinstance(value, typing.ForwardRef) and is_backport_fixable_error(e)):
            raise
        try:
            from eval_type_backport import eval_type_backport
        except ImportError:
            raise TypeError(
                f"You have a type annotation {value.__forward_arg__!r} "
                f"which makes use of newer typing features than are supported in your version of Python. "
                f"To handle this error, you should either remove the use of new syntax "
                f"or install the `eval_type_backport` package."
            ) from e

        return eval_type_backport(value, globalns, localns, try_default=False)


def is_backport_fixable_error(e: TypeError) -> bool:
    msg = str(e)
    return msg.startswith("unsupported operand type(s) for |: ") or "' object is not subscriptable" in msg


if sys.version_info < (3, 10):
    NoneType = type(None)
else:
    from types import NoneType as NoneType


if sys.version_info < (3, 9, 8) or (3, 10) <= sys.version_info < (3, 10, 1):
    def _make_forward_ref(
        arg: typing.Any,
        is_argument: bool = True,
        *,
        is_class: bool = False,
    ) -> typing.ForwardRef:
        """Wrapper for ForwardRef that accounts for the `is_class` argument missing in older versions.
        The `module` argument is omitted as it breaks <3.9.8, =3.10.0 and isn't used in the calls below.

        See https://github.com/python/cpython/pull/28560 for some background.
        The backport happened on 3.9.8, see:
        https://github.com/pydantic/pydantic/discussions/6244#discussioncomment-6275458,
        and on 3.10.1 for the 3.10 branch, see:
        https://github.com/pydantic/pydantic/issues/6912

        Implemented as EAFP with memory.
        """
        return typing.ForwardRef(arg, is_argument)

else:
    _make_forward_ref = typing.ForwardRef

