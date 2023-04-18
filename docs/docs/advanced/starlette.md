# Let's write some code

Now we take the *starlette example* from [usages](/FastDepends/usages/) and specify it to use *Path* now.

## Handle *request* specific fields

First of all, **Starlette** pass to a handler the only one argument - `request`
To use them with `FastDepends` we need unwrap `request` to kwargs.

```python hl_lines="6-8" linenums="1"
{!> docs_src/advanced/custom/starlette.py [ln:1,16-21] !}
```

!!! note ""
    Also, we wraps an original handler to `fast_depends.inject` too at *3* line

## Declare *Custom Field*

Next step, define *Path* custom field

```python linenums="1" hl_lines="8"
{!> docs_src/advanced/custom/starlette.py [ln:2,8-13] !}
```

## Usage with the *Starlette*

And use it at our *Starlette* application:
```python linenums="1" hl_lines="6 7 10"
{!> docs_src/advanced/custom/starlette.py [ln:4-6,23-30] !}
```

Depends is working as expected too

```python linenums="1" hl_lines="1 4-5 9"
def get_user(user_id: int = Path()):
    return f"user {user_id}"

@wrap_starlette
async def hello(user: str = Depends(get_user)):
    return PlainTextResponse(f"Hello, {user}!")

app = Starlette(debug=True, routes=[
    Route("/{user_id}", hello)
])
```

As an *Annotated* does
```python linenums="1" hl_lines="2"
@wrap_starlette
async def get_user(user: Annotated[int, Path()]):
    return PlainTextResponse(f"Hello, {user}!")
```

## Full example

```python linenums="1"
{!> docs_src/advanced/custom/starlette.py !}
```

The code above works "as it". You can copy it and declare other *Header*, *Cookie*, *Query* fields by yourself. Just try, it's fun!