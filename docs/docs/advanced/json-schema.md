# JSON Schema

The `Serializer` attached to a `CallModel` exposes two methods:

* `get_schema()` describes the external inputs of the call: its ordinary
  parameters and inputs of nested and extra dependencies. Injected results and
  `CustomField` arguments are excluded. A call without external inputs produces
  an object with no declared fields.
* `get_response_schema()` describes the configured return type. It returns `None`
  when the return annotation is missing or result serialization is disabled.
  An explicit `-> None` annotation produces a schema for `null`.

Both Pydantic and Msgspec implement this API. Schema generation happens only when
one of these methods is called. Custom serializers can omit schema support; the
default methods raise `NotImplementedError`.

```python
from fast_depends import Depends, Provider
from fast_depends.core import build_call_model
from fast_depends.pydantic import PydanticSerializer


def get_limit(limit: int = 10) -> int:
    return limit


def handler(name: str, limit: int = Depends(get_limit)) -> list[str]:
    return [name] * limit


call = build_call_model(
    handler,
    dependency_provider=Provider(),
    serializer_cls=PydanticSerializer(),
)
assert call.serializer is not None

arguments = call.serializer.get_schema()
response = call.serializer.get_response_schema()
```

Use `MsgSpecSerializer()` from `fast_depends.msgspec` to generate schemas with
Msgspec, including schemas for `msgspec.Struct` types.

Here the input schema contains `name` and the dependency's external `limit`
parameter, with its default of `10`.

The method takes no arguments and uses the existing serializer's backend and
configuration. It reads `CallModel.flat_params` each time, so overrides in the
call's `Provider`, including changes within `Provider.scope()`, appear in the
next schema. For duplicate Python parameter names, the call's own parameter
wins, followed by the first occurrence in a depth-first traversal of dependencies,
then extra dependencies. Aliases are applied by the backend after this collection.

Schema generation does not execute the handler, dependencies, or custom fields.
It builds a separate backend model for the external fields without changing
argument validation, result serialization, or the bound serializer instance.
An override supplied only to an individual `solve()` call is not part of the
bound schema.

A standalone serializer, created directly with `options`, continues to describe
those configured fields. With `inject(cast=False)`, `serializer_cls=None`, or no
installed backend, `call.serializer` can be `None`; the methods require an existing
serializer. `CustomField` schema descriptions are not supported yet.

Schemas retain the backend's native layout. With Pydantic v2, `get_schema()` uses
validation mode, while `get_response_schema()` uses serialization mode to describe
output types and include computed fields. Pydantic v1 uses `definitions`, while
Pydantic v2 and Msgspec use `$defs`. A schema can have a
`$ref` at its root. Keep the definitions with the schema so that nested and
recursive references remain valid. Backend-specific metadata and configuration
are preserved; the methods do not make unsupported types schema-compatible.

The existing `fast_depends.pydantic.schema.get_schema()` helper retains its
`embed`, `resolve_refs`, and `exclude` options and its empty-payload behavior.
