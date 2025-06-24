from fast_depends.dependencies import Provider
from fast_depends.exceptions import ValidationError
from fast_depends.use import Depends, inject
from fast_depends.use import global_provider as dependency_provider

__all__ = (
    "Depends",
    "ValidationError",
    "Provider",
    "dependency_provider",
    "inject",
)
