from typing import Any, List, Optional, Tuple

from pydantic.error_wrappers import ErrorList
from pydantic.fields import ModelField

from fast_depends.types import AnyCallable

RETURN_FIELD = "custom_return"


class Dependant:
    def __init__(
        self,
        *,
        call: Optional[AnyCallable] = None,
        params: Optional[List[ModelField]] = None,
        return_field: Optional[ModelField] = None,
        dependencies: Optional[List["Dependant"]] = None,
        use_cache: bool = True,
        path: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        self.params = params or []
        self.return_field = return_field
        self.dependencies = dependencies or []
        self.call = call
        self.use_cache = use_cache
        # Parent argument name at subdependency
        self.name = name
        # Store the path to be able to re-generate a dependable from it in overrides
        self.path = path
        # Save the cache key at creation to optimize performance
        self.cache_key = (self.call,)

    def cast_response(self, response: Any) -> Tuple[Optional[Any], Optional[ErrorList]]:
        if self.return_field is None:
            return response, []
        return self.return_field.validate(response, {}, loc=RETURN_FIELD)


class Depends:
    def __init__(
        self, dependency: Optional[AnyCallable] = None, *, use_cache: bool = True
    ) -> None:
        self.dependency = dependency
        self.use_cache = use_cache

    def __repr__(self) -> str:
        attr = getattr(self.dependency, "__name__", type(self.dependency).__name__)
        cache = "" if self.use_cache else ", use_cache=False"
        return f"{self.__class__.__name__}({attr}{cache})"
