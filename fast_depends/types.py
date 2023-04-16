from typing import Any, Callable, Dict, TypeVar
from typing_extensions import ParamSpec, TypeAlias

P = ParamSpec("P")

AnyCallable = TypeVar("AnyCallable", bound=Callable[..., Any])
DecoratedCallable: TypeAlias = AnyCallable
AnyDict = TypeVar("AnyDict", bound=Dict[str, Any])
