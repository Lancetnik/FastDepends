from typing import Any

from pydantic import BaseModel

from fast_depends.pydantic._compat import get_model_fields
from tests.marks import pydanticV2


class Model(BaseModel):
    a: int


@pydanticV2
def test_get_model_fields_falls_back_to_model_fields() -> None:
    """Pydantic < 2.11 exposes no `__pydantic_fields__`, only the (now deprecated)
    `model_fields` attribute.
    """

    class WithoutPydanticFields:
        model_fields: dict[str, Any] = dict(get_model_fields(Model))

    assert get_model_fields(WithoutPydanticFields) == (  # type: ignore[arg-type]
        WithoutPydanticFields.model_fields
    )
