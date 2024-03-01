from fast_depends import Depends
from fast_depends.core import build_call_model
from fast_depends.library import CustomField


def test_params():
    def func1(m):
        ...

    def func2(c, b=Depends(func1), d=CustomField()):  # noqa: B008
        ...

    def func3(b):
        ...

    def main(a, b, m=Depends(func2), k=Depends(func3)):
        ...

    def extra_func(n):
        ...

    model = build_call_model(main, extra_dependencies=(Depends(extra_func),))

    assert {p.field_name for p in model.params} == {"a", "b"}
    assert {p.field_name for p in model.flat_params} == {"a", "b", "c", "m", "n"}
