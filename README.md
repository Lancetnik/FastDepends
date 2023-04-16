# FastDepends

<p align="center">
    <a href="https://github.com/Lancetnik/FastDepends/actions/workflows/tests.yml" target="_blank">
        <img src="https://github.com/Lancetnik/FastDepends/actions/workflows/tests.yml/badge.svg" alt="Tests coverage"/>
    </a>
    <a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/lancetnik/fastdepends" target="_blank">
        <img src="https://coverage-badge.samuelcolvin.workers.dev/lancetnik/fastdepends.svg" alt="Coverage">
    </a>
    <a href="https://pypi.org/project/fast-depends" target="_blank">
        <img src="https://img.shields.io/pypi/v/fast-depends?label=pypi%20package" alt="Package version">
    </a>
    <a href="https://pepy.tech/project/fast-depends" target="_blank">
        <img src="https://static.pepy.tech/personalized-badge/fast-depend?period=total&units=international_system&left_color=grey&right_color=blue&left_text=Downloads" alt="downloads"/>
    </a>
    <br/>
    <a href="https://pypi.org/project/fast-depend" target="_blank">
        <img src="https://img.shields.io/pypi/pyversions/fast-depends.svg" alt="Supported Python versions">
    </a>
    <a href="https://github.com/Lancetnik/FastDepends/blob/main/LICENSE" target="_blank">
        <img alt="GitHub" src="https://img.shields.io/github/license/Lancetnik/FastDepends?color=%23007ec6">
    </a>
</p>

---

Documentation: https://lancetnik.github.io/FastDepends/

---

FastDepends - extracted and cleared from HTTP domain logic Fastapi Dependency Injection System.
This is a little library, providing you ability to use lovely Fastapi interfaces at your own
projects or tools.

Thanks to [*fastapi*](https://fastapi.tiangolo.com/) and [*pydantic*](https://docs.pydantic.dev/) projects for this
greate functional. This package just a little change Fasapi sources to provide DI functionality pyre-python way.

Async and sync code supported as well.

## Installation

```bash
pip install fast-depends
```

## Usage

There is no way to make Dependency Injection easier

You can use this library without any frameworks at **sync** and **async** code both

### Async code
```python
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
```

### Sync code
```python
from fast_depends import inject, Depends

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
Syncronous code is fully supported at this package: without any `async_to_sync`, `run_sync`, `syncify` or any other tricks.

Also, *FastDepends* casts function return the same way, it can be very felpfull to build your own tools.

There is two main defferences from native Fastapi DI System.

---

### Note
Library was build by actual **0.95.0 FastAPI** version.

If we'll be too far behind, please, contact [me](mailto:diementros@yandex.ru)
or contubute yourself. Really appreciate your help.
