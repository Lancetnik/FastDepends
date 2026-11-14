from typing import Any

import pytest
from pydantic import BaseModel

from fast_depends import inject
from fast_depends.pydantic import PydanticSerializer


@pytest.mark.parametrize("wrapped", [False, True])
def test_direct_model_keeps_custom_validation(provider, wrapped):
    seen = []

    class Result(BaseModel):
        value: int

        @classmethod
        def model_validate(cls, value: Any, **kwargs: Any):
            seen.append(value)
            return super().model_validate({"value": value["value"] + 1}, **kwargs)

    models = []

    def capture(model):
        models.append(model)
        return model

    @inject(
        serializer_cls=PydanticSerializer(use_fastdepends_errors=wrapped),
        dependency_provider=provider,
        wrap_model=capture,
    )
    def handler() -> Result:
        return {"value": 41}

    value = handler()
    assert value.value == 42
    assert seen == [{"value": 41}]
    assert models[0].serializer.encode_response(value) == b'{"value":42}'
    assert seen == [{"value": 41}]


@pytest.mark.parametrize("wrapped", [False, True])
def test_custom_model_validation_preserves_error_mode(wrapped):
    from pydantic import ValidationError as PydanticValidationError

    from fast_depends.exceptions import ValidationError as FastDependsValidationError

    seen = []

    class Result(BaseModel):
        value: int

        @classmethod
        def model_validate(cls, value: Any, **kwargs: Any):
            seen.append(value)
            return super().model_validate(value, **kwargs)

    serializer = PydanticSerializer(use_fastdepends_errors=wrapped)(
        name="handler", options=[], response_type=Result
    )
    error_type = FastDependsValidationError if wrapped else PydanticValidationError
    with pytest.raises(error_type):
        serializer.response({"value": "invalid"})
    assert seen == [{"value": "invalid"}]
