from abc import ABC
from typing import Optional

from fast_depends.types import AnyDict


class CustomField(ABC):
    param_name: Optional[str]
    cast: bool

    def __init__(self, *, cast: bool = True) -> None:
        self.cast = cast
        self.param_name = None

    def set_param_name(self, name: str) -> "CustomField":
        self.param_name = name

    def use(self, **kwargs: AnyDict) -> AnyDict:
        assert self.param_name, "You should specify `param_name` before using"
        return kwargs
