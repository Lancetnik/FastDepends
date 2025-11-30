---
hide:
  - toc
---

`FastDepends` is a great instrument to integrate with any frameworks you are already using.
It can also be a part of your own tools and frameworks (HTTP or [not*](https://lancetnik.github.io/Propan/) )

There are some usage examples with popular Python HTTP Frameworks:

=== "Flask"
    ```python hl_lines="11-12" linenums="1"
    {!> docs_src/usages/flask.py !}
    ```

=== "Starlette"
    ```python hl_lines="9 17-19" linenums="1"
    {!> docs_src/usages/starlette.py !}
    ```

As you can see above, library, some middlewares and supporting classes... And you can use the whole power of *typed* Python everywhere.

!!! tip
    `FastDepends` raises `pydantic.error_wrappers.ValidationError` at type casting exceptions.

    You need to handle them and wrap them in your own response with your custom middleware if you want to use it
    in production.

!!! note
    <a href="#"></a>
    If you are interested in using `FastDepends` in other frameworks, please take a look
    at my own [**Propan**](https://lancetnik.github.io/Propan/) framework for working with various Message Brokers.
