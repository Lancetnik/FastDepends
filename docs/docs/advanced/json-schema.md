# JSON Schema

The `Serializer` attached to a `CallModel` exposes two methods:

* `get_schema()` describes the arguments configured when the serializer was
  created. A serializer created without arguments produces an object with no
  declared fields.
* `get_response_schema()` describes the configured return type. It returns `None`
  when the return annotation is missing or result serialization is disabled.
  An explicit `-> None` annotation produces a schema for `null`.

Both Pydantic and Msgspec implement this API. Schema generation happens only when
one of these methods is called. Custom serializers can omit schema support; the
default methods raise `NotImplementedError`.

```python
from fast_depends import Provider
from fast_depends.core import build_call_model
from fast_depends.pydantic import PydanticSerializer


def handler(name: str, limit: int = 10) -> list[str]:
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

`get_schema()` describes the arguments validated by this serializer, including
injected arguments. It does not traverse dependency inputs. The method takes no
arguments; its fields and configuration are set when the serializer is created.

Schemas retain the backend's native layout. With Pydantic v2, `get_schema()` uses
validation mode, while `get_response_schema()` uses serialization mode to describe
output types and include computed fields. Pydantic v1 uses `definitions`, while
Pydantic v2 and Msgspec use `$defs`. A schema can have a
`$ref` at its root. Keep the definitions with the schema so that nested and
recursive references remain valid. Backend-specific metadata and configuration
are preserved; the methods do not make unsupported types schema-compatible.

The existing `fast_depends.pydantic.schema.get_schema()` helper retains its
`embed`, `resolve_refs`, and `exclude` options and its empty-payload behavior.
