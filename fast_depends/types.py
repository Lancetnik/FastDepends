from typing import Any, Callable, Dict

from typing_extensions import ParamSpec, TypeAlias

P = ParamSpec("P")

AnyCallable: TypeAlias = Callable[..., Any]
DecoratedCallable: TypeAlias = AnyCallable
AnyDict: TypeAlias = Dict[str, Any]
