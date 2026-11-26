# Shared inputs in FastDepends 4

External arguments are prepared before dependencies run. A handler and its
dependencies share one prepared value when they declare the same input source
and external name or alias. Their types, constraints and transforming validators
must be compatible; otherwise model construction raises `TypeError` with both
declarations.
Overlapping parent and child alias paths, such as `body` and `body.items`, are
unsupported and rejected during preparation. Sibling paths remain supported.

```python
from fast_depends import Depends, inject

def total(items: list[int]):
    items.append(2)
    return sum(items)

@inject
def handler(items: list[int], result: int = Depends(total)):
    return items, result

assert handler(items=["1"]) == ([1, 2], 3)
```

When an input is absent, each consumer retains its own default or default factory.
It is required externally if any consumer requires it. Dependency-only inputs
are keyword-only. Supplied arguments cannot replace an injected dependency
result; use `Provider.override()` instead.
When shared defaults differ, the generated input schema omits a single default
and preserves the combined requiredness.

Validation has two stages. The serializer prepares external values first, then
validates resolved arguments before each function call. Context-dependent
validators and factories can use preceding resolved fields. An input
transformation already applied to a value is not repeated. Unsupported stage
splits raise an error during preparation.

Field validators inside Pydantic models receive that model's own field data.
Validators that need resolved function arguments remain in the second stage.

Custom fields run in declaration order, including asynchronous fields. Replacing
a shared input affects later consumers without repeating input validation.
Existing dependency cache entries remain unchanged; uncached dependencies read
the current value. Context-dependent serializer transformations remain local to
their function.

Override `CustomField.resolve(context, /, **kwargs)` to access framework objects
without colliding with body arguments. Its context comes from
`CallModel.solve(..., context=...)` or `asolve()` and remains separate from
external fields. Existing `use()` and `use_field()` implementations remain
supported.

Each invocation uses one prepared dependency graph, even if an override changes
while it is awaiting. Subsequent calls use the new contract. Nested
`Provider.scope()` blocks restore the enclosing override on exit. Provider
dependency and override mappings are read-only; modify them through its methods.
Graphs with incompatible serializer backends or validation configurations are
rejected during preparation.

Sync/async dispatch and generator context factories are selected during graph
preparation, including for custom fields.

Custom serializers must implement `prepare_fields()`, `prepare_inputs()` and
`validate_resolved()`. The previous `__call__()` interface alone is insufficient
for staged validation. JSON decoding is a separate integration step.
