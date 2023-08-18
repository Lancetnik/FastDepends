from typing import Any, Callable, Dict


class Provider:
    def __init__(self) -> None:
        self.dependency_overrides: Dict[Callable[..., Any], Callable[..., Any]] = {}

    def override(
        self, original: Callable[..., Any], override: Callable[..., Any]
    ) -> None:
        self.dependency_overrides[original] = override

    def clear(self) -> None:
        self.dependency_overrides = {}


dependency_provider = Provider()
