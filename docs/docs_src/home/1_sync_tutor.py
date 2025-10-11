from fast_depends import Depends, inject

def dependency(a: int) -> int:
    return a

@inject
def main(
    a: int,
    b: int,
    c: int = Depends(dependency)
) -> float:
    return a + b + c

assert main("1", 2) == 4.0
