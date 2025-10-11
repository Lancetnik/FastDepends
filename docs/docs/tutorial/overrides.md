# Testing Dependencies with Overrides

## Overriding dependencies during testing

There are some scenarios where you might want to override a dependency during testing.

You don't want the original dependency to run (nor any of the sub-dependencies it might have).

Instead, you want to provide a different dependency that will be used only during tests (possibly only some specific tests), and will provide a value that can be used where the value of the original dependency was used.

### Use cases: external service

An example could be that you have an external authentication provider that you need to call.

You send it a token and it returns an authenticated user.

This provider might be charging you per request, and calling it might take some extra time than if you had a fixed mock user for tests.

You probably want to test the external provider once, but not necessarily call it for every test that runs.

In this case, you can override the dependency that calls that provider, and use a custom dependency that returns a mock user, only for your tests.

### Use the `fast_depends.dependency_provider` object

For these cases, your **FastDepends** library has an object `dependency_provider` with `dependency_overrides` attribute, it is a simple `dict`.

To override a dependency for testing, you put as a key the original dependency (a function), and as the value, your dependency override (another function).

And then **FastDepends** will call that override instead of the original dependency.

```python hl_lines="4 7 10 13 18" linenums="1"
{!> docs_src/tutorial_5_overrides/example.py !}
```

### Use `pytest.fixture`

`dependency_provider` is a library global object. Override dependency at one place, you override it everywhere.

So, if you don't wish to override dependency everywhere, I extremely recommend to use the following fixture for your tests

```python linenums="1" hl_lines="18-21"
{!> docs_src/tutorial_5_overrides/fixture.py !}
```

1.  Drop all overridings

!!! tip
    Alternatively, you can create you own dependency provider in pass it in the functions you want.

    ```python linenums="1" hl_lines="4 12 18"
    from typing import Annotated
    from fast_depends import Depends, Provider, inject

    provider = Provider()

    def abc_func() -> int:
        raise 2

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