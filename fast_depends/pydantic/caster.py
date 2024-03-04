import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple

from fast_depends.library.caster import Caster, OptionItem
from fast_depends.pydantic._compat import (
    PYDANTIC_V2,
    BaseModel,
    ConfigDict,
    PydanticUserError,
    TypeAdapter,
    create_model,
    get_config_base,
    get_model_fields,
)


class PydanticCaster(Caster):
    def __init__(
        self,
        *,
        name: str,
        options: List[OptionItem],
        response_type: Any,
        pydantic_config: Optional[ConfigDict] = None,
    ):
        self.name = name

        class_options = {i.field_name: (i.field_type, i.default_value) for i in options}

        config = get_config_base(pydantic_config)

        self.model = create_model(
            name,
            __config__=config,
            **class_options,
        )

        self.response_callback: Optional[Callable[[Any], Any]] = None
        if response_type and response_type is not inspect.Parameter.empty:
            if issubclass(response_type, BaseModel):
                if PYDANTIC_V2:
                    self.response_callback = lambda x: response_type.model_validate
                else:
                    self.response_callback = lambda x: response_type.validate

            elif PYDANTIC_V2:
                assert TypeAdapter
                try:
                    response_pydantic_type = TypeAdapter(response_type, config=config)
                except PydanticUserError:
                    pass
                else:
                    self.response_callback = response_pydantic_type.validate_python

            if self.response_callback is None:
                response_model = create_model(
                    "ResponseModel",
                    __config__=config,
                    r=(response_type, ...),
                )

                self.response_callback = lambda x: response_model(r=x).r
        else:
            self.response_model = None

    def response(self, value: Any) -> Any:
        if self.response_callback is not None:
            return self.response_callback(value)
        return value

    def __call__(self, options: Dict[str, Any]) -> Dict[str, Any]:
        casted_model = self.model(**options)
        return {
            i: getattr(casted_model, i) for i in get_model_fields(casted_model).keys()
        }

    def get_aliases(self) -> Tuple[str, ...]:
        return tuple(
            f.alias or name for name, f in get_model_fields(self.model).items()
        )
