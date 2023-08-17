from pydantic import BaseModel, create_model
from pydantic.version import VERSION as PYDANTIC_VERSION

PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

if PYDANTIC_V2:
    from pydantic import ConfigDict
    from pydantic._internal._typing_extra import (
        eval_type_lenient as evaluate_forwardref,
    )
    from pydantic.fields import FieldInfo

    class CreateBaseModel(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)

else:
    from pydantic.fields import ModelField as FieldInfo  # type: ignore
    from pydantic.typing import evaluate_forwardref  # type: ignore[no-redef]

    class CreateBaseModel(BaseModel):
        class Config:
            arbitrary_types_allowed = True


__all__ = (
    "BaseModel",
    "CreateBaseModel",
    "FieldInfo",
    "create_model",
    "evaluate_forwardref",
    "PYDANTIC_V2",
)
