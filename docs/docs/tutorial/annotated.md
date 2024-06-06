# Using Annotated

## Why?

Using `Annotated` has several benefits, one of the main ones is that now the parameters of your functions with `Annotated` would not be affected at all.

If you call those functions in other places in your code, the actual default values will be kept, your editor will help you notice missing required arguments, Python will require you to pass required arguments at runtime, you will be able to use the same functions for different things and with different libraries.

Because `Annotated` is standard **Python**, you still get all the benefits from editors and tools, like autocompletion, inline errors, etc.

One of the biggest benefits is that now you can create `Annotated` dependencies that are then shared by multiple path operation functions, this will allow you to reduce a lot of code duplication in your codebase, while keeping all the support from editors and tools.

## Example

For example, you could have code like this:

```python linenums="1" hl_lines="11 15"
{!> docs_src/tutorial_4_annotated/not_annotated.py !}
```

There's a bit of code duplication for the dependency:
```python
user: User = Depends(get_user)
```

...the bigger the codebase, the more noticeable it is.

Now you can create an annotated dependency once, like this:

```python
CurrentUser = Annotated[User, Depends(get_user)]
```

And then you can reuse this `Annotated` dependency:
=== "Python 3.9+"
    ```python linenums="1" hl_lines="11 14 18"
    {!> docs_src/tutorial_4_annotated/annotated_39.py !}
    ```
=== "Python 3.6+"
    ```python linenums="1" hl_lines="11 14 18"
    {!> docs_src/tutorial_4_annotated/annotated_36.py !}
    ```

...and `CurrentUser` has all the typing information as `User`, so your editor will work as expected (autocompletion and everything), and **FastDepends** will be able to understand the dependency defined in `Annotated`. :sunglasses:

## Annotatable variants

You able to use `Field` and `Depends` with `Annotated` as well

=== "Python 3.9+"
    ```python linenums="1"
    {!> docs_src/tutorial_4_annotated/annotated_variants_39.py !}
    ```
=== "Python 3.6+"
    ```python linenums="1"
    {!> docs_src/tutorial_4_annotated/annotated_variants_36.py !}
    ```

## Limitations

Python has a very structured function arguments declaration rules.

```python
def function(
    required_positional_or_keyword_arguments_first,
    default_positional_or_keyword_arguments_second = None.
    *all_unrecognized_positional_arguments,
    required_keyword_only_arguments,
    default_keyword_only_arguments = None,
    **all_unrecognized_keyword_arguments,
): ...
```

!!! warning
    You can not declare **arguments without default** after **default arguments** was declared

So

```python
def func(user_id: int, user: CurrentUser): ...
```

... is a **valid** python code

But
```python
def func(user_id: int | None = None, user: CurrentUser): ...  # invalid code!
```

... is **not**! You can't use the `Annotated` only argument after default argument declaration.

---

There are some ways to write code above correct way:

You can use `Annotated` with a default value

```python
def func(user_id: int | None = None, user: CurrentUser = None): ...
```

Or you you can use `Annotated` with all arguments

```python
UserId = Annotated[int, Field(...)]  # Field(...) is a required
def func(user_id: UserId, user: CurrentUser): ...
```

Also, from the Python view, the following code

```python
# Potential invalid code!
def func(user: CurrentUser, user_id: int | None = None): ...
```

But, **FastDepends** parse positional arguments according their position.

So, calling the function above this way
```python
func(1)
```

Will parses as the following kwargs
```python
{ "user": 1 }
```
And raises error

But, named calling will be correct
```python
func(user_id=1)  # correct calling
```

!!! tip ""
    I really recommend *do not use* `Annotated` as a positional argument

    The best way to avoid all misunderstanding between you and Python - use `pydantic.Field` with `Annotated` everywhere

    Like in the following example

    ```python
    def func(user_id: Annotated[int, Field(...)], user: CurrentUser): ...
    ```