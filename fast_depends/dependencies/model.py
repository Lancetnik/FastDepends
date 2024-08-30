from inspect import unwrap
from typing import Any, Callable


class Dependant:
    use_cache: bool
    cast: bool

    def __init__(
        self,
        dependency: Callable[..., Any],
        *,
        use_cache: bool,
        cast: bool,
        cast_result: bool,
    ) -> None:
        self.dependency = dependency
        self.use_cache = use_cache
        self.cast = cast
        self.cast_result = cast_result

    def __repr__(self) -> str:
        call = unwrap(self.dependency)
        attr = getattr(call, "__name__", type(call).__name__)
        cache = "" if self.use_cache else ", use_cache=False"
        return f"{self.__class__.__name__}({attr}{cache})"
