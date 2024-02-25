# CustomField

!!! warning "Packages developers"
    This is the part of documentation will talks you about some features, that can be helpful to develop your own packages with `FastDepends`

## Custom Arguments Field

If you wish to write your own **FastAPI** or another closely by architecture tool, you
should define your own custom fields to specify application behavior. At **FastAPI** these fields are:

* Body
* Path
* Query
* Header
* Cookie
* Form
* File
* Security

Custom fields can be used to adding something specific to a function arguments (like a *BackgroundTask*) or
parsing incoming objects special way. You able decide by own, why and how you will use these tools.

`FastDepends` grants you this opportunity a very intuitive and comfortable way.

### Let's write *Header*

As an example, will try to implement **FastAPI** *Header* field

```python linenums="1" hl_lines="1 3-4" 
{!> docs_src/advanced/custom/class_declaration.py !}
```

Just import `fast_depends.library.CustomField` and implements `use` (async or sync) method.
That's all. We already have own *Header* field to parse **kwargs** the special way.

### *Header* usage

Now we already can use the *Header* field

```python linenums="1" hl_lines="4 8" 
{!> docs_src/advanced/custom/usage.py !}
```

As we defined, *Header* parse incoming **headers kwargs field**, get a parameter by name and put it to
original function as an argument.

### More details

`CustomField` has some fields you should know about

```python
class CustomField:
    param_name: str
    cast: bool
    required: bool
```

* `param_name` - an original function argument name to replace by your field instance. It was `header_field` at the example above.
* `required` - if CustomField is **required**, raises `pydantic.error_wrappers.ValidationError` if it is not present at final **kwargs**
* `cast` - specify the typecasting behavior. Use *False* to disable pydantic typecasting for fields using with your *CustomField*

```python linenums="1" hl_lines="3 8 12-13"
{!> docs_src/advanced/custom/cast_arg.py !}
```

!!! note
    Pydantic understands only python-native annotation or Pydantic classes. If users will annotate your fields by other classes,
    you should set `cast=False` to avoid pydantic exceptions.

```python
def use(self, **kwargs: AnyDict) -> AnyDict: ...
```

Your *CustimField* objects receive casted to *kwargs* an original function incoming arguments at `use` method.
Returning from the `use` method dict replace an original one. Original function will be executed **with a returned from your fields kwargs**.
Be accurate with.

And one more time:

```python linenums="1" hl_lines="6 9" 
original_kwargs = { "headers": { "field": 1 }}

new_kwargs = Header().set_param_name("field").use(**kwargs)
# new_kwargs = {
#   "headers": { "field": 1 },
#   "field": 1  <-- new field from Header
# }

original_function(**new_kwargs)
```

I hope it was clearly enough right now.

Also, custom fields using according their definition: from left to right.
Next Custom Fields **kwargs** is a return of previous.

An example:

```python linenums="1"
@inject
def func(field1 = Header(), field2 = Header()): ...
```

**field2** incoming kwargs is an output of **field1.use()** 