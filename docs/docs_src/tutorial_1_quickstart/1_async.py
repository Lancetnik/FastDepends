import asyncio

from fast_depends import Depends, inject

async def simple_dependency(a: int, b: int = 3):
    return a + b

def another_dependency(a: int):
    return a

@inject
async def method(
    a: int,
    b: int = Depends(simple_dependency),
    c: int = Depends(another_dependency),
):
    return a + b + c

assert asyncio.run(method("1")) == 6
