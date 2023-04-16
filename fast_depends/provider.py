from typing import Dict

from fast_depends.types import AnyCallable


class Provider:
    def __init__(self):
        self.dependency_overrides: Dict[AnyCallable, AnyCallable] = {}

    def override(self, original: AnyCallable, override: AnyCallable) -> None:
        self.dependency_overrides[original] = override

    def clear(self) -> None:
        self.dependency_overrides = {}


dependency_provider = Provider()
