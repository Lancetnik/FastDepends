from fast_depends import Depends, inject

def another_dependency(a: int):
    return a * 2

def simple_dependency(a: int, b: int = Depends(another_dependency)): # (1)
    return a + b

@inject
def method(
    a: int,
    b: int = Depends(another_dependency),
    c: int = Depends(simple_dependency)
):
    return a + b + c

assert method("1") == 6
