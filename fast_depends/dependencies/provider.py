from collections.abc import Callable, Hashable, Iterator, Mapping
from contextlib import contextmanager
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, TypeAlias

from fast_depends.core import build_call_model

if TYPE_CHECKING:
    from fast_depends.core import CallModel


Key: TypeAlias = Hashable


class Provider:
    def __init__(self) -> None:
        self._dependencies: dict[Key, CallModel] = {}
        self._overrides: dict[Key, CallModel] = {}
        self.revision = 0

    @property
    def dependencies(self) -> Mapping[Key, "CallModel"]:
        return MappingProxyType(self._dependencies)

    @property
    def overrides(self) -> Mapping[Key, "CallModel"]:
        return MappingProxyType(self._overrides)

    def merge(self, provider: "Provider") -> "Provider":
        p = Provider()
        p._dependencies = self._dependencies | provider._dependencies
        p._overrides = self._overrides | provider._overrides
        return p

    def clear(self) -> None:
        self._overrides.clear()
        self.revision += 1

    def add_dependant(
        self,
        dependant: "CallModel",
    ) -> Key:
        key = self.__get_original_key(dependant.call)
        self._dependencies[key] = dependant
        self.revision += 1
        return key

    def get_dependant(self, key: Key) -> "CallModel":
        return self._overrides.get(key) or self._dependencies[key]

    def override(
        self,
        original: Callable[..., Any],
        override: Callable[..., Any],
    ) -> None:
        key = self.__get_original_key(original)

        serializer_cls = None

        if original_dependant := self._dependencies.get(key):
            serializer_cls = original_dependant.serializer_cls

        else:
            self._dependencies[key] = build_call_model(
                original,
                dependency_provider=self,
            )

        override_model = build_call_model(
            override,
            dependency_provider=self,
            serializer_cls=serializer_cls,
        )

        self._overrides[key] = override_model
        self.revision += 1

    def __setitem__(
        self,
        key: Callable[..., Any],
        value: Callable[..., Any],
    ) -> None:
        """Alias for `provider[key] = value` syntax"""
        self.override(key, value)

    @contextmanager
    def scope(
        self,
        original: Callable[..., Any],
        override: Callable[..., Any],
    ) -> Iterator[None]:
        key = self.__get_original_key(original)
        previous = self._overrides.get(key)
        self.override(original, override)
        try:
            yield
        finally:
            if previous is None:
                self._overrides.pop(key, None)
            else:
                self._overrides[key] = previous
            self.revision += 1

    def __get_original_key(self, original: Callable[..., Any]) -> Key:
        return original
