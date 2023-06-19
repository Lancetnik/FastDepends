from typing import Any, Callable


class Depends:
    use_cache: bool
    cast: bool

    def __init__(
        self,
        call: Callable[..., Any],
        *,
        use_cache: bool = True,
        cast: bool = True,
    ) -> None:
        self.call = call
        self.use_cache = use_cache
        self.cast = cast

    def __repr__(self) -> str:
        attr = getattr(self.call, "__name__", type(self.call).__name__)
        cache = "" if self.use_cache else ", use_cache=False"
        return f"{self.__class__.__name__}({attr}{cache})"
