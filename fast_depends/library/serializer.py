from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


class OptionItem:
    __slots__ = (
        "field_name",
        "field_type",
        "default_value",
    )

    def __init__(
        self,
        field_name: str,
        field_type: Any,
        default_value: Any = ...,
    ) -> None:
        self.field_name = field_name
        self.field_type = field_type
        self.default_value = default_value


class Serializer(ABC):
    name: str

    @abstractmethod
    def __init__(
        self,
        *,
        name: str,
        options: List[OptionItem],
        response_type: Any,
        **extra: Any,
    ):
        raise NotImplementedError()

    @abstractmethod
    def __call__(self, options: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()

    def get_aliases(self) -> Tuple[str, ...]:
        return ()

    def response(self, value: Any) -> Any:  # pragma: no cover
        return value
