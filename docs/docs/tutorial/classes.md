# Classes as Dependencies

### "Callable", remember?

```python linenums="1"
{!> docs_src/tutorial_2_classes/tutorial_1.py !}
```

Yep, all of these examples can be used as a dependency!

---

### INIT (1-st call)

You can use class initializer as a dependency. This way, object of this class
will be the type of your dependency:

```python linenums="1" hl_lines="5-6 9"
{!> docs_src/tutorial_2_classes/tutorial_2.py !}
```

!!! warning
    You should use `Any` annotation if `MyDependency` is not a `pydantic.BaseModel` subclass.
    Using `MyDependency` annotation raises `ValueError` exception at code initialization time as the pydantic
    can't cast any value to not-pydantic class.

---

### CALL (2-nd call)

If you wish to specify your dependency behavior earlier, you can use `__call__` method of
already initialized class object.

```python linenums="1" hl_lines="7-8 11"
{!> docs_src/tutorial_2_classes/tutorial_3.py !}
```

---

### CLASSMETHOD or STATICMETHOD (3-rd call)

Also, you can use classmethods or staticmethod as dependencies.
It can be helpful with some OOP patterns (Strategy as an example).

```python linenums="1" hl_lines="4-6 9"
{!> docs_src/tutorial_2_classes/tutorial_4.py !}
```

---

### ANY METHOD (4-th call)

```python linenums="1" hl_lines="7-8 11"
{!> docs_src/tutorial_2_classes/tutorial_5.py !}
```


!!! tip "Async"
    Only *3-rd* and *4-th* call methods are able to be `async` type
