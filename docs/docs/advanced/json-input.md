# Prepared JSON input

`prepare_json_call()` prepares calls from JSON bytes, including `Depends`, extra
dependencies and custom fields through the ordinary dependency solver.

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

Prepare outside the message loop to reuse the decoder. Await async calls.

`embed=True` uses the whole document for one parameter instead of named arguments.
Each prepared callable keeps its body mode without changing the call model.

Msgspec directly validates bytes for a plain handler or an embedded dependency
chain with a single body consumer and no custom fields or extra dependencies.
Return values and injected results retain ordinary validation. Other graphs and
serializers use decoded Python arguments before solving dependencies. Pydantic
keeps Python validation, including strict date validation.

Pass `None` instead of bytes with `load_arguments` to use a framework's cached body.
The callback returns `(args, kwargs)`; async calls also accept an awaitable result.
With bytes, it is used only on the Python-argument path, before dependencies or
fields execute. Changes to the prepared dependency chain and supplied keyword
arguments also select that path. Without a callback, stdlib JSON decoding is used.
In named mode, JSON object fields override supplied
keywords; with `embed=True`, supplied keywords override positional body values.

`prepare_json_call()` returns `None` for a generator root or root body parameters
that are positional-only or variadic.
Preparation never executes dependencies or fields.

Custom serializers implement `get_json_decoder(embed=False)` to return a reusable
decoder from bytes to validated arguments by Python name, including aliased
fields. The default returns `None`.

Msgspec's native syntax and numeric limits can differ from stdlib JSON:
`NaN`/`Infinity` and out-of-range numbers are rejected. Validation errors follow
`use_fastdepends_errors`; syntax errors retain native exceptions.

Do not retry ordinary decoding after a native error: hooks may already have run.
Repeated keys can invoke hooks per occurrence; the last value is used.
