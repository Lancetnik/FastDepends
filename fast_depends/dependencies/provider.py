from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator


class Provider:
    dependency_overrides: Dict[Callable[..., Any], Callable[..., Any]]

    def __init__(self) -> None:
        self.dependency_overrides = {}

    def clear(self) -> None:
        self.dependency_overrides = {}

    def override(
        self,
        original: Callable[..., Any],
        override: Callable[..., Any],
    ) -> None:
        self.dependency_overrides[original] = override

    @contextmanager
    def scope(
        self,
        original: Callable[..., Any],
        override: Callable[..., Any],
    ) -> Iterator[None]:
        self.dependency_overrides[original] = override
        yield
        self.dependency_overrides.pop(original, None)


dependency_provider = Provider()
