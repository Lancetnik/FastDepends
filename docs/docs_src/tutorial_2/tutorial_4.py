from fast_depends import inject, Depends

class MyDependency:
    @staticmethod
    def dep(a: int):
        return a ** 2

@inject
def func(d: int = Depends(MyDependency.dep)):
    return d

assert func(a=3) == 9