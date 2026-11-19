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

Prepare once to reuse the decoder; await async calls.

`embed=True` uses the whole document for one parameter instead of named arguments.
Each prepared callable keeps its body mode without changing the call model.

Msgspec can validate bytes directly for plain handlers and simple embedded chains
with one body consumer, no custom fields and no extra dependencies. Other cases
use Python arguments through the ordinary solver, including Pydantic's strict
Python date validation. Injected results and return values retain normal validation.

Pass `None` with `load_arguments` to use a framework's cached body. The callback
returns `(args, kwargs)`; async calls also accept an awaitable result. With bytes,
it runs only on the Python-argument path, before dependencies or fields. Changes to the
prepared dependency chain or supplied keywords select that path. Without a callback,
that path uses stdlib JSON decoding. In named mode, body fields override supplied
keywords; with `embed=True`, keywords override positional body values.

`prepare_json_call()` returns `None` for a generator root or root body parameters
that are positional-only or variadic.
Preparation never executes dependencies or fields.

Custom serializers provide `get_json_decoder(embed=False)`: a reusable decoder
from bytes to validated arguments by Python name, including aliased fields.
The default returns `None`.

Native Msgspec decoding rejects `NaN`/`Infinity` and out-of-range numbers.
`use_fastdepends_errors` controls validation wrapping; syntax errors stay native.
Hooks may run per repeated key, with the last value used. Never retry ordinary
decoding after a native error:
hooks may already have run.
