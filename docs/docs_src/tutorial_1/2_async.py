import asyncio
from fast_depends import inject, Depends

def another_dependency(a: int):
    return a * 2

async def simple_dependency(a: int, b: int = Depends(another_dependency)): # (1)
    return a + b

@inject
async def method(
    a: int,
    b: int = Depends(simple_dependency),
    c: int = Depends(another_dependency),
):
    return a + b + c

assert asyncio.run(method("1")) == 6