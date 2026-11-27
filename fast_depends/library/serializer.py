import inspect
import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Hashable, Iterable, Sequence
from typing import Any, Protocol

from fast_depends.library.schema_processing import SchemaExclude


class PreparedValue:
    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value


class InputField:
    __slots__ = (
        "option",
        "key",
        "paths",
        "required",
        "contract",
        "schema",
        "schema_option",
    )

    def __init__(
        self,
        option: "OptionItem",
        *,
        key: Hashable,
        paths: tuple[tuple[str | int, ...], ...],
        required: bool,
        contract: Any,
        schema: Any,
        schema_option: "OptionItem | None" = None,
    ) -> None:
        self.option = option
        self.key = key
        self.paths = paths
        self.required = required
        self.contract = contract
        self.schema = schema
        self.schema_option = schema_option or option


class PreparedInputs(Protocol):
    def __call__(self, values: dict[str, Any], /) -> dict[Hashable, PreparedValue]: ...


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

    def prepare_fields(self) -> dict[str, InputField]:
        raise TypeError(f"{type(self).__name__} does not support staged input validation")

    def prepare_inputs(self, fields: Sequence[InputField]) -> PreparedInputs:
        raise TypeError(f"{type(self).__name__} does not support shared input validation")

    def validate_resolved(self, values: dict[str, Any]) -> dict[str, Any]:
        raise TypeError(f"{type(self).__name__} does not support staged input validation")

    def _prepare_call(
        self, *, staged: bool
    ) -> Callable[[dict[str, Any]], dict[str, Any]]:
        return self.validate_resolved if staged else self

    def get_schema(
        self,
        *,
        embed: bool = False,
        exclude: Iterable[SchemaExclude] = (),
        resolve_refs: bool = False,
    ) -> dict[str, Any]:
        """Describe external inputs, or configured fields when used standalone."""
        raise NotImplementedError

    def get_response_schema(self) -> dict[str, Any] | None:
        """Describe the return type, or return None when it is not configured.

        An explicit ``None`` annotation produces a JSON Schema for null.
        Schema generation is optional for custom serializers.
        """
        raise NotImplementedError

    def encode(self, value: Any) -> bytes:
        """Encode a validated return value using this call's response contract.

        Custom serializers may implement this independently of validation.
        """
        raise NotImplementedError

    @abstractmethod
    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def response(self, value: Any) -> Any:
        return value


def _encode_json(message: Any) -> bytes:
    return json.dumps(message).encode("utf-8")


class SerializerProto(Protocol):
    # Encoders may be bound to a factory's configuration.
    encode: Callable[[Any], bytes] = staticmethod(_encode_json)

    def __call__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ) -> Serializer: ...
