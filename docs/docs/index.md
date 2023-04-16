---
hide:
  - toc
---

# FastDepends

FastDepends - Fastapi dependency injection system extracted from Fastapi and cleared of all HTTP logic.
This is a small library which provides you with the ability to use lovely Fastapi interfaces in your own
projects or tools.

Thanks to [*fastapi*](https://fastapi.tiangolo.com/) and [*pydantic*](https://docs.pydantic.dev/) projects for this
greate functionality. This package is just a small change of the original Fastapi sources to provide DI functionality in a pyre-Python way.

Async and sync modes are both supported.

## Installation

<div class="termy">
```console
$ pip install fast-depends
---> 100%
```
</div>

## Usage

There is no way to make Dependency Injection easier

You can use this library without any frameworks in both **sync** and **async** code.

=== "Async code"
    ```python hl_lines="8-13" linenums="1"
    {!> docs_src/home/1_async_tutor.py !}
    ```

=== "Sync code"
    ```python hl_lines="6-11" linenums="1"
    {!> docs_src/home/1_sync_tutor.py !}
    ```

`@inject` decorator plays multiple roles at the same time:

* resolve *Depends* classes
* cast types according to Python annotation
* validate incoming parameters using *pydantic*

!!! tip
    Synchronous code is fully supported in this package: without any `async_to_sync`, `run_sync`, `syncify` or any other tricks.

    Also, *FastDepends* casts functions' return values the same way, it can be very helpful in building your own tools.

    These are two main defferences from native Fastapi DI System.   

!!! warning ""
    Library was based on **0.95.0 FastAPI** version.

    If we are too far behind, please, contact [me](mailto:diementros@yandex.ru) or contubute yourself. Really appreciate your help.
