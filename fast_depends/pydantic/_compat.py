from typing import Any, Optional

from pydantic import BaseModel, create_model
from pydantic.version import VERSION as PYDANTIC_VERSION

__all__ = (
    "BaseModel",
    "create_model",
    "PYDANTIC_V2",
    "get_config_base",
    "ConfigDict",
    "TypeAdapter",
    "PydanticUserError",
)


PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

default_pydantic_config = {"arbitrary_types_allowed": True}

# isort: off
if PYDANTIC_V2:
    from pydantic import ConfigDict, TypeAdapter
    from pydantic.fields import FieldInfo
    from pydantic.errors import PydanticUserError

    def model_schema(model: type[BaseModel]) -> dict[str, Any]:
        return model.model_json_schema()

    def get_config_base(config_data: Optional[ConfigDict] = None) -> ConfigDict:
        return config_data or ConfigDict(**default_pydantic_config)  # type: ignore[typeddict-item]

    def get_aliases(model: type[BaseModel]) -> tuple[str, ...]:
        return tuple(f.alias or name for name, f in model.model_fields.items())

    def get_model_fields(model: type[BaseModel]) -> dict[str, FieldInfo]:
        return model.model_fields

else:
    from pydantic.config import get_config, ConfigDict, BaseConfig
    from pydantic.fields import ModelField

    TypeAdapter = None
    PydanticUserError = Exception

    def get_config_base(config_data: Optional[ConfigDict] = None) -> type[BaseConfig]:  # type: ignore[misc]
        return get_config(config_data or ConfigDict(**default_pydantic_config))  # type: ignore[typeddict-item]

    def model_schema(model: type[BaseModel]) -> dict[str, Any]:
        return model.schema()

    def get_aliases(model: type[BaseModel]) -> tuple[str, ...]:
        return tuple(f.alias or name for name, f in model.__fields__.items())

    def get_model_fields(model: type[BaseModel]) -> dict[str, ModelField]:
        return model.__fields__
