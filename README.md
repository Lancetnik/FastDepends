# FastDI

---

Documentation: https://lancetnik.github.io/FastDI/

---

FastDI - extracted and cleared from HTTP domain logic Fastapi Dependency Injection System.
This is a little library, providing you ability to use lovely Fastapi interfaces at your own
projects or tools.

Thanks to [*fastapi*](https://fastapi.tiangolo.com/) and [*pytest*](https://docs.pytest.org/en/7.3.x/) projects for this
greate functional. This package just a little change Fasapi sources to provide DI functionality pyre-python way.

## Usage

There is no way to make Dependency Injection easier

You can use this library without any frameworks at **sync** and **async** code both

### Async code
```python
import asyncio

from fastdi import inject, Depends

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
```

### Sync code
```python
from fastdi import inject, Depends

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
```

`@inject` decorator playing multiple roles at the same time:

* resolve *Depends* classes
* cast types according python annotation
* validate incoming parameters using *pydantic*

---

### Features
Syncronous code is fully supported at this package: without any `async_to_sync`, `run_sync`, `syncify` or any another tricks.

Also, *FastDI* casts function return the same way, it can be very felpfull to build your own tools.

There is two main defferences from native Fastapi DI System.

---

### Note
Library was build by actual **0.95.0 FastAPI** version.

If we'll be too far behind, please, contact [me](mailto:diementros@yandex.ru)
or contubute yourself. Really appreciate your help.
