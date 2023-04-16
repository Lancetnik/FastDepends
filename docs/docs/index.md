---
hide:
  - toc
---

# FastDepends

FastDepends - extracted and cleared from HTTP domain logic Fastapi Dependency Injection System.
This is a little library, providing you ability to use lovely Fastapi interfaces at your own
projects or tools.

Thanks to [*fastapi*](https://fastapi.tiangolo.com/) and [*pydantic*](https://docs.pydantic.dev/) projects for this
greate functional. This package just a little change Fasapi sources to provide DI functionality pyre-python way.

Async and sync code supported as well.

## Installation

<div class="termy">
```console
$ pip install fast-depends
---> 100%
```
</div>

## Usage

There is no way to make Dependency Injection easier

You can use this library without any frameworks at **sync** and **async** code both

=== "Async code"
    ```python hl_lines="8-13" linenums="1"
    {!> docs_src/home/1_async_tutor.py !}
    ```

=== "Sync code"
    ```python hl_lines="6-11" linenums="1"
    {!> docs_src/home/1_sync_tutor.py !}
    ```

`@inject` decorator playing multiple roles at the same time:

* resolve *Depends* classes
* cast types according python annotation
* validate incoming parameters using *pydantic*

!!! tip
    Syncronous code is full supported at this package: without any `async_to_sync`, `run_sync`, `syncify` or any other tricks.
    
    Also, *FastDepends* casts function return the same way, it can be very felpfull to build your own tools.
    
    There is two main defferences from native Fastapi DI System.

!!! warning ""
    Library was build by actual **0.95.0 FastAPI** version.

    If we'll be too far behind, please, contact [me](mailto:diementros@yandex.ru)
    or contubute yourself. Really appreciate your help. 