# Pydantic Field

`FastDepends` is able to use `pydantic.Field` as a default parameter to validate incoming argument

```python linenums="1" hl_lines="5"
from pydantic import Field
from fast_depends import inject

@inject
def func(a: str = Field(..., max_length=32)):
    ...
```

!!! note "Pydantic Documentation"
    To get more information and usage examples, please visit official [pydantic documentation](https://docs.pydantic.dev/usage/schema/#field-customization)

All available fields are:

* `default`: (a positional argument) the default value of the field.
    Since the `Field` replaces the field's default, this first argument can be used to set the default.
    Use ellipsis (`...`) to indicate the field is required.
* `default_factory`: a zero-argument callable that will be called when a default value is needed for this field.
    Among other purposes, this can be used to set dynamic default values.
    It is forbidden to set both `default` and `default_factory`.
* `alias`: the public name of the field
* `const`: this argument *must* be the same as the field's default value if present.
* `gt`: for numeric values (``int``, `float`, `Decimal`), adds a validation of "greater than" and an annotation
  of `exclusiveMinimum` to the JSON Schema
* `ge`: for numeric values, this adds a validation of "greater than or equal" and an annotation of `minimum` to the
  JSON Schema
* `lt`: for numeric values, this adds a validation of "less than" and an annotation of `exclusiveMaximum` to the
  JSON Schema
* `le`: for numeric values, this adds a validation of "less than or equal" and an annotation of `maximum` to the
  JSON Schema
* `multiple_of`: for numeric values, this adds a validation of "a multiple of" and an annotation of `multipleOf` to the
  JSON Schema
* `max_digits`: for `Decimal` values, this adds a validation to have a maximum number of digits within the decimal. It
  does not include a zero before the decimal point or trailing decimal zeroes.
* `decimal_places`: for `Decimal` values, this adds a validation to have at most a number of decimal places allowed. It
  does not include trailing decimal zeroes.
* `min_items`: for list values, this adds a corresponding validation and an annotation of `minItems` to the
  JSON Schema
* `max_items`: for list values, this adds a corresponding validation and an annotation of `maxItems` to the
  JSON Schema
* `unique_items`: for list values, this adds a corresponding validation and an annotation of `uniqueItems` to the
  JSON Schema
* `min_length`: for string values, this adds a corresponding validation and an annotation of `minLength` to the
  JSON Schema
* `max_length`: for string values, this adds a corresponding validation and an annotation of `maxLength` to the
  JSON Schema
* `allow_mutation`: a boolean which defaults to `True`. When False, the field raises a `TypeError` if the field is
  assigned on an instance.  The model config must set `validate_assignment` to `True` for this check to be performed.
* `regex`: for string values, this adds a Regular Expression validation generated from the passed string and an
  annotation of `pattern` to the JSON Schema