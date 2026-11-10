import inspect
import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Protocol


class OptionItem:
    __slots__ = (
        "field_name",
        "field_type",
        "default_value",
        "kind",
        "source",
    )

    def __init__(
        self,
        field_name: str,
        field_type: Any,
        source: Any = None,
        default_value: Any = ...,
        kind: inspect._ParameterKind = inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ) -> None:
        self.field_name = field_name
        self.field_type = field_type
        self.default_value = default_value
        self.source = source
        self.kind = kind

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
        self.options = {i.field_name: i for i in options}
        self.response_option = {
            "return": OptionItem(field_name="return", field_type=response_type),
        }
        # Bound calls provide current external inputs, including dependency overrides.
        self._schema_options: Callable[[], list[OptionItem]] | None = None

    def get_aliases(self) -> tuple[str, ...]:
        return ()

    def get_schema(self) -> dict[str, Any]:
        """Describe external inputs, or configured fields when used standalone."""
        raise NotImplementedError

    def get_response_schema(self) -> dict[str, Any] | None:
        """Describe the return type, or return None when it is not configured.

        An explicit ``None`` annotation produces a JSON Schema for null.
        Schema generation is optional for custom serializers.
        """
        raise NotImplementedError

    @abstractmethod
    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def response(self, value: Any) -> Any:
        return value


class SerializerProto(Protocol):
    def __call__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ) -> Serializer: ...

    @staticmethod
    def encode(message: Any) -> bytes:
        return json.dumps(message).encode("utf-8")
