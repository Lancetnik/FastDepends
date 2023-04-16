---
hide:
  - toc
---

# How it works

At first, I suppose, we need to discuss about this tool's key concept.

It is very simple:

1. At your code's initialization time `FastDepends` builds special *pydantic* model with your function's expected arguments as a model fields, builds the dependencies graph
2. At runtime `FastDepends` grabs all incoming functions' `*args, **kwargs` and initializes functions' representation models with them
3. At the next step `FastDepends` fills model fields with functions' dependencies
4. Finally, `FastDepends` catches functions' outputs and casts it to expected `return` type

This is pretty close to the following code:

```python linenums="1"
{!> docs_src/how-it-works/works.py !}
```

!!! note
    It is not the real code, but generally `FastDepends` works this way

So, the biggest part of the `FastDepends` code execution happens on application startup.
At runtime the library just casts types to already built models. It works really fast.
Generally, the library works with the same speed as the `pydantic` - the main dependency.

On the other hand, working with only `*args, **kwargs` allows the library to be independent
from other frameworks, business domains, technologies, etc. You are free to decide for
yourself, how exactly to use this tool.