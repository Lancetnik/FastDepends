from fast_depends import Depends, Provider
from fast_depends.core import build_call_model
from fast_depends.library import CustomField


def test_params():
    def func1(m): ...

    def func2(c, b=Depends(func1), d=CustomField()):  # noqa: B008
        ...

    def func3(b): ...

    def main(a, b, m=Depends(func2), k=Depends(func3)): ...

    def extra_func(n): ...

    model = build_call_model(
        main, extra_dependencies=(Depends(extra_func),), dependency_provider=Provider()
    )

    assert {p.field_name for p in model.params} == {"a", "b"}
    assert {p.field_name for p in model.flat_params} == {"a", "b", "c", "m", "n"}


def test_args_kwargs_params():
    def func1(m): ...

    def func2(c, b=Depends(func1), d=CustomField()):  # noqa: B008
        ...

    def func3(b): ...

    def default_var_names(a, *args, b, m=Depends(func2), k=Depends(func3), **kwargs):
        return a, args, b, kwargs

    def extra_func(n): ...

    model = build_call_model(
        default_var_names,
        extra_dependencies=(Depends(extra_func),),
        dependency_provider=Provider(),
    )

    assert {p.field_name for p in model.params} == {"a", "args", "b", "kwargs"}
    assert {p.field_name for p in model.flat_params} == {
        "a",
        "args",
        "b",
        "kwargs",
        "c",
        "m",
        "n",
    }

    assert default_var_names(1, *("a"), b=2, **{"kw": "kw"}) == (
        1,
        ("a",),
        2,
        {"kw": "kw"},
    )


def test_custom_args_kwargs_params():
    def func1(m): ...

    def func2(c, b=Depends(func1), d=CustomField()):  # noqa: B008
        ...

    def func3(b): ...

    def extra_func(n): ...

    def custom_var_names(a, *args_, b, m=Depends(func2), k=Depends(func3), **kwargs_):
        return a, args_, b, kwargs_

    model = build_call_model(
        custom_var_names,
        extra_dependencies=(Depends(extra_func),),
        dependency_provider=Provider(),
    )

    assert {p.field_name for p in model.params} == {"a", "args_", "b", "kwargs_"}
    assert {p.field_name for p in model.flat_params} == {
        "a",
        "args_",
        "b",
        "kwargs_",
        "c",
        "m",
        "n",
    }

    assert custom_var_names(1, *("a"), b=2, **{"kw": "kw"}) == (
        1,
        ("a",),
        2,
        {"kw": "kw"},
    )
