from abc import ABC, abstractmethod
from typing import Any, Protocol


class OptionItem:
    __slots__ = (
        "field_name",
        "field_type",
        "default_value",
        "source",
    )

    def __init__(
        self,
        field_name: str,
        field_type: Any,
        source: Any = None,
        default_value: Any = ...,
    ) -> None:
        self.field_name = field_name
        self.field_type = field_type
        self.default_value = default_value
        self.source = source

    def __repr__(self) -> str:
        type_name = getattr(self.field_type, "__name__", str(self.field_type))
        content = f"{self.field_name}, type=`{type_name}`"
        if self.default_value is not Ellipsis:
            content = f"{content}, default=`{self.default_value}`"
        if self.source:
            content = f"{content}, source=`{self.source}`"
        return f"OptionItem[{content}]"


class Serializer(ABC):
    def __init__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ):
        self.name = name
        self.options = {
            i.field_name: i for i in options
        }
        self.response_option = {
            "return": OptionItem(field_name="return", field_type=response_type),
        }


    @abstractmethod
    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def get_aliases(self) -> tuple[str, ...]:
        return ()

    def response(self, value: Any) -> Any:
        return value


class SerializerProto(Protocol):
    def __call__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ) -> Serializer:
        ...
