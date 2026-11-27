# Staged validation

Serializers provide three methods for integrations that prepare external inputs
before resolving dependencies:

- `prepare_fields()` describes each external parameter, including its aliases,
  validation contract and default policy.
- `prepare_inputs(fields)` returns a callable that validates external values.
  Pass one compatible field definition per shared input. The result maps shared
  input keys to `PreparedValue` instances.
- `validate_resolved(arguments)` validates a function's resolved arguments.
  External arguments use `PreparedValue`; computed arguments use ordinary values.

An integration maps shared keys back to each function's parameter names:

```python
from inspect import Parameter

from fast_depends.library.serializer import OptionItem
from fast_depends.pydantic import PydanticSerializer

serializer = PydanticSerializer()(
    name="handler", options=[OptionItem("value", int)], response_type=Parameter.empty
)
fields = serializer.prepare_fields()
prepare = serializer.prepare_inputs(tuple(fields.values()))
inputs = prepare({"value": "1"})
assert serializer.validate_resolved({"value": inputs[fields["value"].key]}) == {"value": 1}
```

Validation completed during input preparation is not repeated for that value.
When a value is absent, leave its argument out so that each consumer's default or
factory applies at the resolved stage. Context-dependent Pydantic validators can use preceding resolved arguments;
unsupported validation splits raise `TypeError` during preparation.

Input preparation cannot mix serializer backends or incompatible validation
settings. Pydantic aliases can contain nested paths; Msgspec uses a single field
alias. Native metadata, model validation and configured hooks remain in effect.

Custom serializers implement these methods to support staged calls. Their
`__call__()` method remains available for ordinary argument validation.
