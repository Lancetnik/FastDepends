import asyncio

from fast_depends import inject, Depends

async def dependency(a: int) -> int:
    return a

@inject
async def main(
    a: int,
    b: int,
    c: int = Depends(dependency)
) -> float:
    return a + b + c

assert asyncio.run(main("1", 2)) == 4.0