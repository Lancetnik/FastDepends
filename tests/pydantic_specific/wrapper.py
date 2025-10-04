from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any


def noop_wrap(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return wrapper
