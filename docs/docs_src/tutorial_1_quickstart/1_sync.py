from fast_depends import inject, Depends

def simple_dependency(a: int, b: int = 3):
    return a + b

@inject
def method(a: int, d: int = Depends(simple_dependency)):
    return a + d

assert method("1") == 5