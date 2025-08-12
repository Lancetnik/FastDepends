from abc import ABC
from typing import Any, Optional, TypeVar

Cls = TypeVar("Cls", bound="CustomField")


class CustomField(ABC):
    param_name: Optional[str]
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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(required={self.required}, cast={self.cast})"
