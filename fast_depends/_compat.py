import sys
from importlib.metadata import version as get_version
from typing import Any

__all__ = (
    "ExceptionGroup",
    "evaluate_forwardref",
)


ANYIO_V3 = get_version("anyio").startswith("3.")

try:
    from fast_depends.pydantic._compat import evaluate_forwardref
except ImportError:
    def evaluate_forwardref(annotation: Any, *args: Any, **kwargs: Any):
        return annotation

if ANYIO_V3:
    from anyio import ExceptionGroup as ExceptionGroup
else:
    if sys.version_info < (3, 11):
        from exceptiongroup import ExceptionGroup as ExceptionGroup
    else:
        ExceptionGroup = ExceptionGroup
