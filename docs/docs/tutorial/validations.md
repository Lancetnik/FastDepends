# Pydantic Field

`FastDI` is able to use `pydantic.Field` as a default parameter to validate incoming argument

```python linenums="1" hl_lines="5"
from pydantic import Field
from fastdi import inject

@inject
def func(a: str = Field(..., max_length=32)):
    ...
```

All available fields are:

* **default**: since this is replacing the field’s default, its first argument is used
to set the default, use ellipsis (``...``) to indicate the field is required

* **default_factory**: callable that will be called when a default value is needed for this field
If both `default` and `default_factory` are set, an error is raised.

* **alias**: the public name of the field

* **const**: this field is required and *must* take it's default value

* **gt**: only applies to numbers, requires the field to be "greater than". The schema
will have an ``exclusiveMinimum`` validation keyword

* **ge**: only applies to numbers, requires the field to be "greater than or equal to". The
schema will have a ``minimum`` validation keyword

* **lt**: only applies to numbers, requires the field to be "less than". The schema
will have an ``exclusiveMaximum`` validation keyword

* **le**: only applies to numbers, requires the field to be "less than or equal to". The
schema will have a ``maximum`` validation keyword

* **multiple_of**: only applies to numbers, requires the field to be "a multiple of". The
schema will have a ``multipleOf`` validation keyword

* **allow_inf_nan**: only applies to numbers, allows the field to be NaN or infinity (+inf or -inf),
which is a valid Python float. Default True, set to False for compatibility with JSON.

* **max_digits**: only applies to Decimals, requires the field to have a maximum number
of digits within the decimal. It does not include a zero before the decimal point or trailing decimal zeroes.

* **decimal_places**: only applies to Decimals, requires the field to have at most a number of decimal places
allowed. It does not include trailing decimal zeroes.

* **min_items**: only applies to lists, requires the field to have a minimum number of
elements. The schema will have a ``minItems`` validation keyword

* **max_items**: only applies to lists, requires the field to have a maximum number of
elements. The schema will have a ``maxItems`` validation keyword

* **unique_items**: only applies to lists, requires the field not to have duplicated
elements. The schema will have a ``uniqueItems`` validation keyword

* **min_length**: only applies to strings, requires the field to have a minimum length. The
schema will have a ``minLength`` validation keyword

* **max_length**: only applies to strings, requires the field to have a maximum length. The
schema will have a ``maxLength`` validation keyword

* **allow_mutation**: a boolean which defaults to True. When False, the field raises a TypeError if the field is
assigned on an instance.  The BaseModel Config must set validate_assignment to True

* **regex**: only applies to strings, requires the field match against a regular expression
pattern string. The schema will have a ``pattern`` validation keyword
