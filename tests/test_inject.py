from fast_depends import Depends, Provider, inject
from fast_depends.core import build_call_model


def dep() -> int:
    return 1


def func(d: int = Depends(dep)) -> int:
    return d


def test_inject_reuses_a_prebuilt_model() -> None:
    """`inject()` accepts an already built `CallModel` instead of building one.

    This is what integrations (e.g. FastStream) rely on to build the model once,
    inspect it, and only then wrap the call.
    """
    provider = Provider()
    model = build_call_model(func, dependency_provider=provider)

    injected = inject(None, dependency_provider=provider)(func, model)

    assert injected() == 1
