from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, create_model
from pydantic.version import VERSION as PYDANTIC_VERSION

__all__ = (
    "BaseModel",
    "create_model",
    "evaluate_forwardref",
    "PYDANTIC_V2",
    "get_config_base",
    "ConfigDict",
)


PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

default_pydantic_config = {"arbitrary_types_allowed": True}

evaluate_forwardref: Any
# isort: off
if PYDANTIC_V2:
    from pydantic import ConfigDict
    from pydantic._internal._typing_extra import (  # type: ignore[no-redef]
        eval_type_lenient as evaluate_forwardref,
    )
    from pydantic import FieldInfo

    def model_schema(model: Type[BaseModel]) -> Dict[str, Any]:
        return model.model_json_schema()

    def get_config_base(config_data: Optional[ConfigDict] = None) -> ConfigDict:
        return config_data or ConfigDict(**default_pydantic_config)  # type: ignore[typeddict-item]

    def get_model_fields(model: BaseModel) -> Dict[str, FieldInfo]:
        return model.model_fields

else:
    from pydantic.typing import evaluate_forwardref as evaluate_forwardref  # type: ignore[no-redef]
    from pydantic.config import get_config, ConfigDict, BaseConfig
    from pydantic.fields import ModelField

    def get_config_base(config_data: Optional[ConfigDict] = None) -> Type[BaseConfig]:  # type: ignore[misc]
        return get_config(config_data or ConfigDict(**default_pydantic_config))  # type: ignore[typeddict-item]

    def model_schema(model: Type[BaseModel]) -> Dict[str, Any]:
        return model.schema()

    def get_model_fields(model: BaseModel) -> Dict[str, ModelField]:
        return model.__fields__
