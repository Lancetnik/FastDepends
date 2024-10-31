from fast_depends import Depends, inject


class MyDependency:
    def __init__(self, a: int):
        self.field = a

    def __call__(self, b: int):
        return self.field + b

@inject
def func(d: int = Depends(MyDependency(3))):
    return d

assert func(b=3) == 6
