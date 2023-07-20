from fast_depends.core import build_call_model
from fast_depends.use import inject


def base_func(a: int) -> str:
    return "success"


def test_prebuild():
    model = build_call_model(base_func)
    inject()(None, model)(1)
