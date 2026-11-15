# Prepared JSON input

For calls without dependencies or custom fields, a supporting serializer can
validate JSON bytes directly into typed arguments. This avoids creating a separate
untyped Python representation before argument validation.

```python
from fast_depends import Provider
from fast_depends.core import build_call_model
from fast_depends.msgspec import MsgSpecSerializer


def add(a: int, *, b: int = 2) -> int:
    return a + b


model = build_call_model(
    add,
    serializer_cls=MsgSpecSerializer(),
    dependency_provider=Provider(),
)
invoke = model.prepare_json_call()
assert invoke is not None
assert invoke(b'{"a": "40"}') == 42
```

Prepare the callable outside the message loop. The Msgspec decoder is created at
preparation and reused; arguments use one native validation pass without a second
conversion of the decoded result. Return-value
validation retains the configured serializer behavior. For an async call, await
the prepared callable's result.

`embed=True` treats the JSON document as the value of a single parameter, rather
than an object containing named arguments. Distinct prepared callables can use
different body modes without changing the call model.

`prepare_json_call()` returns `None` for serializers without native JSON support,
dependencies, extra dependencies, custom fields, positional-only parameters,
variadic parameters, generators, or an unsupported body mode. Keep the existing
object-based invocation for these cases. Preparation never executes dependencies
or fields. Pydantic retains its Python validation path; JSON-mode validation can
have different semantics, including for strict date fields.

The serializer capability is `get_json_decoder(embed=False)`. Its result is a
reusable callable accepting bytes and returning validated arguments by Python
parameter name, including when wire aliases are used. Custom serializers opt in
by implementing this method; the default returns `None`.

Native input uses Msgspec's JSON syntax and numeric range rules. Non-standard
`NaN`/`Infinity` tokens and out-of-range numbers are rejected. This can differ from
parsing with the standard library before Python validation. Validation failures
respect `use_fastdepends_errors`; JSON syntax errors retain the native decoder
exception. Do not retry object decoding after native validation has started:
user hooks may already have executed.

Hooks follow native JSON decoding. Repeated object keys can cause a hook to run
for each occurrence, even though the last value is used for the argument.
