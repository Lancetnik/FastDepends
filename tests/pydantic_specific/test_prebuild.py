from __future__ import annotations

from pydantic import BaseModel

from fast_depends import Provider
from fast_depends.core import build_call_model
from fast_depends.pydantic import PydanticSerializer
from fast_depends.pydantic._compat import PYDANTIC_V2

from .wrapper import noop_wrap


class Model(BaseModel):
    a: str


def model_func(m: Model) -> str:
    return m.a


def test_prebuild_with_wrapper():
    func = noop_wrap(model_func)
    assert func(Model(a="Hi!")) == "Hi!"

    # build_call_model should work even if function is wrapped with a
    # wrapper that is imported from different module
    call_model = build_call_model(
        func,
        dependency_provider=Provider(),
        serializer_cls=PydanticSerializer(),
    )

    model = call_model.serializer.model
    assert model
    # Fails if function unwrapping is not done at type introspection

    if PYDANTIC_V2:
        model.model_rebuild()
    else:
        # pydantic v1
        modelmodel.update_forward_refs()
