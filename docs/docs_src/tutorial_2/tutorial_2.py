from typing import Any
from fast_depends import inject, Depends

class MyDependency:
    def __init__(self, a: int):
        self.field = a

@inject
def func(d: Any = Depends(MyDependency)):
    return d.field

assert func(a=3) == 3