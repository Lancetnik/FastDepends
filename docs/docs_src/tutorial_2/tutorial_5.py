from fast_depends import inject, Depends

class MyDependency:
    def __init__(self, a):
        self.field = a

    def dep(self, a: int):
        return self.field + a

@inject
def func(d: int = Depends(MyDependency(3).dep)):
    return d

assert func(a=3) == 6