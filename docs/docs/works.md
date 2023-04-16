---
hide:
  - toc
---

# How it works

At first, I suppose, we need to disscuss about this tool key concept.

It is a very simple thing:

1. At your code initializing time `FastDepends` build special *pydantic* model with your function expected arguments as a model fields
2. At runtime `FastDepends` grab all incoming function `*args, **kwargs` and initialize functional representation model with them
3. Next step `FastDepends` provides model fields to original function
4. Finally, `FastDepends` catch function output and casts it to expected `return` type

It's a pretty close to the following code:

```python linenums="1"
{!> docs_src/how-it-works/works.py !}
```

!!! note
    It's not the real code, but generally `FastDepends` works this way

So, most past of the `FastDepends` code execution accounting for application startup.
At the runtime library just casts types to already builded models. It's working really fast.
Generally, library works with the same speed as the `pydantic` - the main dependcy.

At the over hande, using only `*args, **kwargs` to working with allows library be free
from different frameworks, business domains, technologies, etc. You are free to dicede for
yourself, how exactly use this tool.