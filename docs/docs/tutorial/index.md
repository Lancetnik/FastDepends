# Quickstart

I suppose, if you are already here, you are exactly known about this library usage.

It is using the same way as [FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/) is.

But, I can remember you, if it's nessesary.

## Basic usage

=== "Sync"
    ```python hl_lines="3-4" linenums="1"
    {!> docs_src/tutorial_1/1_sync.py !}
    ```

=== "Async"
    ```python hl_lines="4-5 7-8" linenums="1"
    {!> docs_src/tutorial_1/1_async.py !}
    ```

    !!! tip "Be accurate"
        At **async** code we can use **sync and async **dependencies both, but at **sync** runtime
        only **sync** dependencies are available.

**First step**: we need to declare our dependency: it can be any Callable object.

??? note "Callable"
    "Callable" - object is able to be "called". It can be any function, class, or class method.

    Another words: if we can write following the code `my_object()` - `my_object` is "Callable"

=== "Sync"
    ```python hl_lines="2" linenums="6"
    {!> docs_src/tutorial_1/1_sync.py [ln:5-8]!}
    ```

=== "Async"
    ```python hl_lines="1 4 5" linenums="10"
    {!> docs_src/tutorial_1/1_async.py [ln:10-16]!}
    ```

**Second step**: declare dependency required with `Depends`

=== "Sync"
    ```python hl_lines="3 5" linenums="6"
    {!> docs_src/tutorial_1/1_sync.py [ln:5-10]!}
    ```

=== "Async"
    ```python hl_lines="7 9" linenums="10"
    {!> docs_src/tutorial_1/1_async.py [ln:10-18]!}
    ```

**Last step**: just use the dependencies calling result!

That was easy, isn't it?

!!! tip "Auto @inject"
    At the code above you can note, that original `Depends` functions wasn't decorated by `@inject`.

    It's true: all dependencies are decorated by default at using. Keep it at your mind.

## Nested Dependencies

Dependecies are also able to contain their own dependencies. There is nothing unexpected with this case:
just declare `Depends` requirement at original dependency function.

=== "Sync"
    ```python linenums="1" hl_lines="3-4 6-7 12-13"
    {!> docs_src/tutorial_1/2_sync.py !}
    ```

    1. Call another_dependency here

=== "Async"
    ```python linenums="1" hl_lines="4-5 7-8 13-14"
    {!> docs_src/tutorial_1/2_async.py !}
    ```

    1. Call another_dependency here

!!! Tip "Cache"
    At the examples above `another_dependency` was called **AT ONCE!**.
    `FastDepends` cashes all dependecies responses throw **ONE** `@inject` callstask.
    It means, that all nested dependencies give a one-time cached response. But,
    with different injected function calls, cache will differ too.

    To disable that behavior, just use `Depends(..., cache=False)`. This way dependency will
    be executed each time.


## Dependencies type casting

If you remember, `FastDepends` casts function `return` too. This means, dependecy output
will be casted twice: at dependecy function *out* and at the injector *in*. Nothing bad,
if they are the same type, nothing overhead occures. Just keep it in your mind. Or don't...
My work is done anyway.

```python linenums="1"
from fast_depends import inject, Depends

def simple_dependency(a: int, b: int = 3) -> str:
    return a + b  # cast 'return' to str first time

@inject
def method(a: int, d: int = Depends(simple_dependency)):
    # cast 'd' to int second time
    return a + d

assert method("1") == 5
```

Also, `return` type will be cached. If you are using this dependcy at `N` functions,
cached return will be casted `N` times.

To avoid this problem use [mypy](https://www.mypy-lang.org) to check types at your project or
just be accurate with your outer annotations.