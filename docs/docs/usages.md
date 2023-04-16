---
hide:
  - toc
---

`FastDI` is a great instrument to integrate with any frameworks you are already using.
Also it able to be a part of your own tools and frameworks (HTTP or [not*](https://lancetnik.github.io/Propan/) )

There are some usage examples with populare Python HTTP Frameworks:

=== "Flask"
    ```python hl_lines="11-12" linenums="1"
    {!> docs_src/usages/flask.py !}
    ```

=== "Starlette"
    ```python hl_lines="9 16-18" linenums="1"
    {!> docs_src/usages/starlette.py !}
    ```

As you see above, library, some middlewares and supporting classes... And you able to use
all power of *typed* python everywhere.

!!! tip
    `FastDI` raises `pydantic.error_wrappers.ValidationError` at casting types exceptions.

    Handle and wrap it to correct response with your custom middleware if you want to use it
    at production.

!!! note
    <a href="#"></a>
    If you are interesting of `FastDI` using in other framework, please, take a look
    at my own [**Propan**](https://lancetnik.github.io/Propan/) framework to working with different Message Brokers. 