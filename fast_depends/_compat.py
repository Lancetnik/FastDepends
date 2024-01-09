import sys
from importlib.metadata import version as get_version
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, create_model
from pydantic.version import VERSION as PYDANTIC_VERSION

__all__ = (
    "BaseModel",
    "FieldInfo",
    "create_model",
    "evaluate_forwardref",
    "PYDANTIC_V2",
    "get_config_base",
    "get_model_fields",
    "ConfigDict",
    "ExceptionGroup",
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
    from pydantic.fields import FieldInfo

    def get_config_base(config_data: Optional[ConfigDict] = None) -> ConfigDict:
        return config_data or ConfigDict(**default_pydantic_config)  # type: ignore[typeddict-item]

    def get_model_fields(model: Type[BaseModel]) -> Dict[str, FieldInfo]:
        return model.model_fields

    class CreateBaseModel(BaseModel):
        """Just to support FastStream < 0.3.7."""

        model_config = ConfigDict(arbitrary_types_allowed=True)

else:
    from pydantic.fields import ModelField as FieldInfo  # type: ignore
    from pydantic.typing import evaluate_forwardref as evaluate_forwardref  # type: ignore[no-redef]
    from pydantic.config import get_config, ConfigDict, BaseConfig

    def get_config_base(config_data: Optional[ConfigDict] = None) -> Type[BaseConfig]:  # type: ignore[misc]
        return get_config(config_data or ConfigDict(**default_pydantic_config))  # type: ignore[typeddict-item]

    def get_model_fields(model: Type[BaseModel]) -> Dict[str, FieldInfo]:
        return model.__fields__  # type: ignore[return-value]

    class CreateBaseModel(BaseModel):  # type: ignore[no-redef]
        """Just to support FastStream < 0.3.7."""

        class Config:
            arbitrary_types_allowed = True


ANYIO_V3 = get_version("anyio").startswith("3.")

if ANYIO_V3:
    from anyio import ExceptionGroup as ExceptionGroup
else:
    if sys.version_info < (3, 11):
        from exceptiongroup import ExceptionGroup as ExceptionGroup
    else:
        ExceptionGroup = ExceptionGroup
