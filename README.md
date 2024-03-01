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
        <img src="https://static.pepy.tech/personalized-badge/fast-depends?period=month&units=international_system&left_color=grey&right_color=blue" alt="downloads"/>
    </a>
    <br/>
    <a href="https://pypi.org/project/fast-depends" target="_blank">
        <img src="https://img.shields.io/pypi/pyversions/fast-depends.svg" alt="Supported Python versions">
    </a>
    <a href="https://github.com/Lancetnik/FastDepends/blob/main/LICENSE" target="_blank">
        <img alt="GitHub" src="https://img.shields.io/github/license/Lancetnik/FastDepends?color=%23007ec6">
    </a>
</p>

---

Documentation: <https://lancetnik.github.io/FastDepends/>

---

FastDepends - FastAPI Dependency Injection system extracted from FastAPI and cleared of all HTTP logic.
This is a small library which provides you with the ability to use lovely FastAPI interfaces in your own
projects or tools.

Thanks to [*fastapi*](https://fastapi.tiangolo.com/) and [*pydantic*](https://docs.pydantic.dev/) projects for this
great functionality. This package is just a small change of the original FastAPI sources to provide DI functionality in a pure-Python way.

Async and sync modes are both supported.

# For why?

This project should be extremely helpful to boost your not-**FastAPI** applications (even **Flask**, I know that u like some legacy).

Also the project can be a core of your own framework for anything. Actually, it was build for my another project - :rocket:[**Propan**](https://github.com/Lancetnik/Propan):rocket: (and [**FastStream**](https://github.com/airtai/faststream)), check it to see full-featured **FastDepends** usage example.

## Installation

```bash
pip install fast-depends
```

## Usage

There is no way to make Dependency Injection easier

You can use this library without any frameworks in both **sync** and **async** code.

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

`@inject` decorator plays multiple roles at the same time:

* resolve *Depends* classes
* cast types according to Python annotation
* validate incoming parameters using *pydantic*

---

### Features

Synchronous code is fully supported in this package: without any `async_to_sync`, `run_sync`, `syncify` or any other tricks.

Also, *FastDepends* casts functions' return values the same way, it can be very helpful in building your own tools.

These are two main defferences from native FastAPI DI System.

---

### Dependencies Overriding

Also, **FastDepends** can be used as a lightweight DI container. Using it, you can easily override basic dependencies with application startup or in tests.

```python
from typing import Annotated

from fast_depends import Depends, dependency_provider, inject

def abc_func() -> int:
    raise NotImplementedError()

def real_func() -> int:
    return 1

@inject
def func(
    dependency: Annotated[int, Depends(abc_func)]
) -> int:
    return dependency

with dependency_provider.scope(abc_func, real_func):
    assert func() == 1
```

`dependency_provider` in this case is just a default container already declared in the library. But you can use your own the same way:

```python
from typing import Annotated

from fast_depends import Depends, Provider, inject

provider = Provider()

def abc_func() -> int:
    raise NotImplementedError()

def real_func() -> int:
    return 1

@inject(dependency_overrides_provider=provider)
def func(
    dependency: Annotated[int, Depends(abc_func)]
) -> int:
    return dependency

with provider.scope(abc_func, real_func):
    assert func() == 1
```

This way you can inherit the basic `Provider` class and define any extra logic you want!

---

### Custom Fields

If you wish to write your own FastAPI or another closely by architecture tool, you should define your own custom fields to specify application behavior.

Custom fields can be used to adding something specific to a function arguments (like a BackgroundTask) or parsing incoming objects special way. You able decide by own, why and how you will use these tools.

FastDepends grants you this opportunity a very intuitive and comfortable way.

```python
from fast_depends import inject
from fast_depends.library import CustomField

class Header(CustomField):
    def use(self, /, **kwargs: AnyDict) -> AnyDict:
        kwargs = super().use(**kwargs)
        kwargs[self.param_name] = kwargs["headers"][self.param_name]
        return kwargs

@inject
def my_func(header_field: int = Header()):
    return header_field

assert my_func(
    headers={ "header_field": "1" }
) == 1
```
