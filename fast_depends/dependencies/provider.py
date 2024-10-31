from collections.abc import Hashable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable

from typing_extensions import TypeAlias

from fast_depends.core import build_call_model

if TYPE_CHECKING:
    from fast_depends.core import CallModel


Key: TypeAlias = Hashable


class Provider:
    dependencies: dict[Key, "CallModel"]
    overrides: dict[Key, "CallModel"]

    def __init__(self) -> None:
        self.dependencies = {}
        self.overrides = {}

    def clear(self) -> None:
        self.dependencies = {}
        self.overrides = {}

    def add_dependant(
        self,
        dependant: "CallModel",
    ) -> Key:
        key = self.__get_original_key(dependant.call)
        self.dependencies[key] = dependant
        return key

    def get_dependant(self, key: Key) -> "CallModel":
        return self.overrides.get(key) or self.dependencies[key]

    def override(
        self,
        original: Callable[..., Any],
        override: Callable[..., Any],
    ) -> None:
        key = self.__get_original_key(original)

        override_model = build_call_model(
            override,
            dependency_provider=self,
        )

        if (original_dependant := self.dependencies.get(key)):
            override_model.serializer = original_dependant.serializer

        else:
            self.dependencies[key] = build_call_model(
                original,
                dependency_provider=self,
            )

        self.overrides[key] = override_model

    @contextmanager
    def scope(
        self,
        original: Callable[..., Any],
        override: Callable[..., Any],
    ) -> Iterator[None]:
        self.override(original, override)
        yield
        self.overrides.pop(self.__get_original_key(original), None)

    def __get_original_key(self, original: Callable[..., Any]) -> Key:
        return original
