from fast_depends import Provider, inject
from fast_depends.core import build_call_model


def base_func(a: int) -> str:
    return "success"


def test_prebuild():
    model = build_call_model(base_func, dependency_provider=Provider())
    inject()(None, model)(1)
