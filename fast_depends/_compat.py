from pydantic import BaseModel, create_model
from pydantic.version import VERSION as PYDANTIC_VERSION

PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

if PYDANTIC_V2:
    from pydantic._internal._typing_extra import (
        eval_type_lenient as evaluate_forwardref,
    )
else:
    from pydantic.typing import evaluate_forwardref  # type: ignore[no-redef]


__all__ = (
    "BaseModel",
    "create_model",
    "evaluate_forwardref",
    "PYDANTIC_V2",
)
