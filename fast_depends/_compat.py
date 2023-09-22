from typing import Any

from pydantic import BaseModel, create_model
from pydantic.version import VERSION as PYDANTIC_VERSION

PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

evaluate_forwardref: Any
# isort: off
if PYDANTIC_V2:
    from pydantic import ConfigDict
    from pydantic._internal._typing_extra import (  # type: ignore[no-redef]
        eval_type_lenient as evaluate_forwardref,
    )
    from pydantic.fields import FieldInfo

    class CreateBaseModel(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)

else:
    from pydantic.fields import ModelField as FieldInfo  # type: ignore
    from pydantic.typing import evaluate_forwardref as evaluate_forwardref  # type: ignore[no-redef]

    class CreateBaseModel(BaseModel):  # type: ignore[no-redef]
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
