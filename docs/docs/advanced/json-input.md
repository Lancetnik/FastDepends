# Prepared JSON input

`prepare_json_call()` prepares Msgspec calls from JSON bytes without an untyped
intermediate body or a second argument conversion.

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

Prepare outside the message loop to reuse the decoder. Arguments use one native
validation pass; validation of return values is preserved. Await async calls.

`embed=True` uses the whole document for one parameter instead of named arguments.
Each prepared callable keeps its body mode without changing the call model.

`None` means use ordinary injection: unsupported serializers (including Pydantic),
dependencies or extra dependencies, custom fields, positional-only or variadic
parameters, generators, or incompatible body modes. Preparation never executes
dependencies or fields. Pydantic keeps Python validation; strict date validation
differs in JSON mode.

Custom serializers implement `get_json_decoder(embed=False)` to return a reusable
decoder from bytes to validated arguments by Python name, including aliased
fields. The default returns `None`.

Msgspec's native syntax and numeric limits can differ from stdlib JSON:
`NaN`/`Infinity` and out-of-range numbers are rejected. Validation errors follow
`use_fastdepends_errors`; syntax errors retain native exceptions.

Do not retry ordinary decoding after a native error: hooks may already have run.
Repeated keys can invoke hooks per occurrence; the last value is used.
