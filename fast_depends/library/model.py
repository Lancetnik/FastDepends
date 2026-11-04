from abc import ABC
from typing import Any, TypeVar

from fast_depends.library.schema import SchemaField
from fast_depends.library.serializer import OptionItem

Cls = TypeVar("Cls", bound="CustomField")


class CustomField(ABC):
    param_name: str | None
    cast: bool
    required: bool

    __slots__ = (
        "cast",
        "param_name",
        "required",
        "field",
    )

    def __init__(
        self,
        *,
        cast: bool = True,
        required: bool = True,
    ) -> None:
        self.cast = cast
        self.param_name = None
        self.required = required
        self.field = False

    def set_param_name(self: Cls, name: str) -> Cls:
        self.param_name = name
        return self

    def use(self, /, **kwargs: Any) -> dict[str, Any]:
        assert self.param_name, "You should specify `param_name` before using"
        return kwargs

    def use_field(self, kwargs: dict[str, Any]) -> None:
        raise NotImplementedError

    def get_schema(self, parameter: OptionItem) -> SchemaField | None:
        """Describe an external input, or return None to hide this injected field.

        The parameter retains its declared type, metadata and default before
        runtime cast/required transformations. This hook must not execute the field.
        """
        return None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(required={self.required}, cast={self.cast})"
