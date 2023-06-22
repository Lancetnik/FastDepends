from typing import Any, Callable


class Depends:
    use_cache: bool
    cast: bool

    def __init__(
        self,
        dependency: Callable[..., Any],
        *,
        use_cache: bool = True,
        cast: bool = True,
    ) -> None:
        self.dependency = dependency
        self.use_cache = use_cache
        self.cast = cast

    def __repr__(self) -> str:
        attr = getattr(self.dependency, "__name__", type(self.dependency).__name__)
        cache = "" if self.use_cache else ", use_cache=False"
        return f"{self.__class__.__name__}({attr}{cache})"
