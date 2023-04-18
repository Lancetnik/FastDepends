# Generators

Sometimes we want to call something *before* and *after* original funtion call.

That purpouse can be reached by using `yield` keyword.

## A database dependency with yield

For example, you could use this to create a database session and close it after finishing.

Only the code prior `yield` statement is executed before sending a response
```python linenums="1" hl_lines="1-2"
{!> docs_src/tutorial_3_yield/tutorial_1.py !}
```

The *yielded* value is what is injected into original function
```python linenums="1" hl_lines="3"
{!> docs_src/tutorial_3_yield/tutorial_1.py !}
```

The code following the `yield` statement is executed after the original function has been called
```python linenums="1" hl_lines="4"
{!> docs_src/tutorial_3_yield/tutorial_1.py !}
```

!!! tip
    As same as a regular depends behavior you can use `async` and `sync` declarations both with an `async` original function
    and only `sync` declaration with a `sync` one.

!!! warning
All errors occures at original function or another dependencies will be raised this place
```python linenums="1" hl_lines="3"
{!> docs_src/tutorial_3_yield/tutorial_1.py !}
```
To guarantee `db.close()` execution use the following code:
```python linenums="1" hl_lines="3 5"
{!> docs_src/tutorial_3_yield/tutorial_2.py !}
```