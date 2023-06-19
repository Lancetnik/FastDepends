from abc import ABC
from typing import Any, Dict, Optional, TypeVar

Cls = TypeVar("Cls", bound="CustomField")


class CustomField(ABC):
    param_name: Optional[str]
    cast: bool
    required: bool

    def __init__(self, *, cast: bool = True, required: bool = True) -> None:
        self.cast = cast
        self.param_name = None
        self.required = required

    def set_param_name(self: Cls, name: str) -> Cls:
        self.param_name = name
        return self

    def use(self, **kwargs: Dict[str, Any]) -> Dict[str, Any]:
        assert self.param_name, "You should specify `param_name` before using"
        return kwargs
