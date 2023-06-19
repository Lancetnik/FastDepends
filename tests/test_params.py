from fast_depends import Depends
from fast_depends.core import build_call_model


def test_params():
    def func1(a):
        ...

    def func2(c, b=Depends(func1)):
        ...

    def func3(b):
        ...

    def main(a, b, m=Depends(func2), k=Depends(func3), c=Depends(func1)):
        ...

    model = build_call_model(main)

    assert model.real_params == {"a", "b"}
    assert model.flat_params == {"a", "b", "c"}
