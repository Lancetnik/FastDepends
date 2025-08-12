from pydantic import BaseModel

from fast_depends import Provider, inject
from fast_depends.core import build_call_model

from .wrapper import noop_wrap


class Model(BaseModel):
    a: str


def base_func(a: int) -> str:
    return "success"


def test_prebuild():
    model = build_call_model(base_func, dependency_provider=Provider())
    inject()(None, model)(1)


def test_prebuild_with_wrapper() -> None:
    func = noop_wrap(model_func)
    assert func(Model(a="Hi!")) == "Hi!"

    # build_call_model should work even if function is wrapped with a
    # wrapper that is imported from different module
    call_model = build_call_model(func)

    assert call_model.model
    # Fails if function unwrapping is not done at type introspection

    if hasattr(call_model.model, "model_rebuild"):
        call_model.model.model_rebuild()
    else:
        # pydantic v1
        call_model.model.update_forward_refs()
