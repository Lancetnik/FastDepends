# JSON Schema

The `Serializer` attached to a `CallModel` exposes two methods:

* `get_schema()` describes the external inputs of the call: its ordinary
  parameters and inputs of nested and extra dependencies. Injected results and
  hidden `CustomField` arguments are excluded. A call without external inputs produces
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

The method uses the existing serializer's backend and configuration. Its optional
keyword arguments control schema processing (see below); it does not accept
`options`. It reads ordinary inputs and custom field descriptions each time, so overrides in the
call's `Provider`, including changes within `Provider.scope()`, appear in the
next schema. For duplicate Python parameter names, the call's own parameter
wins, followed by the first occurrence in a depth-first traversal of dependencies,
then extra dependencies. Aliases are applied by the backend after this collection.

Schema generation does not execute the handler, dependencies, or custom field
`use()` / `use_field()` methods. It calls custom fields' schema hooks.
It builds a separate backend model for the external fields without changing
argument validation, result serialization, or the bound serializer instance.
An override supplied only to an individual `solve()` call is not part of the
bound schema.

A standalone serializer, created directly with `options`, continues to describe
those configured fields. With `inject(cast=False)`, `serializer_cls=None`, or no
installed backend, `call.serializer` can be `None`; the methods require an existing
serializer.

Schemas retain the backend's native layout. Pydantic input schemas use validation
mode. Response schemas describe `call.serializer.encode_response(value)` in
serialization mode, including computed fields and annotation serializers.
Getting a schema does not change argument validation or Python return values.

## Encoding typed responses

The serializer attached to a call exposes `encode_response(value) -> bytes`.
Pass it an already validated return value. With Pydantic, it uses the same
cached `TypeAdapter` for response validation, JSON encoding, and response schemas.
`PlainSerializer` and `WrapSerializer` on return annotations are honored, including
serializers wrapping an entire model. Aliases apply to models, dataclasses and
`TypedDict` responses. Model subclasses are encoded using the declared return
type's fields, following Pydantic's normal rules.

```python
from typing import Annotated

from pydantic import PlainSerializer

from fast_depends import Provider, inject
from fast_depends.core import build_call_model
from fast_depends.pydantic import PydanticSerializer

factory = PydanticSerializer()
TextInt = Annotated[int, PlainSerializer(str, return_type=str)]


def answer() -> TextInt:
    return 42


call = build_call_model(
    answer, dependency_provider=Provider(), serializer_cls=factory
)
answer = inject(serializer_cls=factory)(answer, model=call)
assert call.serializer is not None

value = answer()
assert type(value) is int
assert factory.encode(value) == b"42"
assert call.serializer.encode_response(value) == b'"42"'
assert call.serializer.get_response_schema() == {"type": "string"}
```

`@inject` still returns the validated Python value. It does not implicitly encode
JSON. Each call retains its own adapter, so a factory shared by handlers with
different return annotations keeps their encoding contracts independent.
Encoding errors come from Pydantic's serializer; response validation errors keep
the existing FastDepends/Pydantic error handling.

Pydantic configuration follows the adapter's normal precedence. Ordinary typed
values and containers use the factory configuration. Models and dataclasses use
their own configuration. A directly annotated model, dataclass or `TypedDict`
rejects an adapter-level config in Pydantic, so FastDepends creates its adapter
without the factory config. A `TypedDict`'s own `ser_json_*` settings are ignored
by Pydantic's encoder: nested dictionaries inherit the surrounding serializer's
JSON options, and a root `TypedDict` uses defaults. Response schemas account for
this behavior, including shared named aliases under different configurations and
numeric temporal encoding on Pydantic 2.12/2.13.

The existing factory-level `encode(value)` remains a generic encoder. It has no
return annotation and applies the factory's JSON encoding settings to ordinary
values. Model instances keep their own serializers and configuration. Class-level
`PydanticSerializer.encode(value)` retains default encoding. Custom factory
`encode` overrides also apply to untyped bound responses.

Typed Pydantic `encode_response()` always produces JSON, including for root
`bytes`: with `ser_json_bytes="base64"`, `b"ab"` becomes `b'"YWI="'`, and the
response schema has `format: base64url`. Use `factory.encode(b"ab")` for raw
transport bytes; it continues to return `b"ab"` unchanged. This distinction also
allows serializers attached to `Annotated[bytes, ...]` to run.

Without a return annotation, or with `cast_result=False` / `serialize_result=False`,
`encode_response()` uses the factory's generic encoder and
`get_response_schema()` returns `None`. Msgspec exposes `encode_response()` using
its existing encoder. Custom serializers can omit this optional method; its base
implementation raises `NotImplementedError`.

### FastStream

FastStream's regular publication path receives the factory and calls its generic
encoder. To publish using a handler's return annotation, explicitly encode through
its bound serializer and set the JSON content type:

```python
from faststream.rabbit import RabbitBroker, RabbitResponse

broker = RabbitBroker(serializer=factory)


@broker.publisher("answers")
@broker.subscriber("requests")
async def publish_answer():
    value = answer()
    return RabbitResponse(
        call.serializer.encode_response(value), content_type="application/json"
    )
```

Here `answer`, `call`, and `factory` are from the preceding example. The published
JSON value is `"42"`. Direct `await broker.publish(42, "answers")` still publishes
a number. Existing subscriber return annotations are not automatically forwarded
to the factory's encoder; integrations must select the bound serializer explicitly.
The same rule applies to AG2 integrations that use `serialize_result=False` and
encode tool results separately.

Pydantic and Msgspec use `$defs`. A schema can have a
`$ref` at its root. Keep the definitions with the schema so that nested and
recursive references remain valid. Backend-specific metadata and configuration
are preserved; the methods do not make unsupported types schema-compatible.

## Processing input schemas

Both backends support the same keyword-only options:

```python
arguments = call.serializer.get_schema(
    exclude=("internal", ("headers", "debug")),
    embed=True,
    resolve_refs=True,
)
```

* `exclude=()` removes inputs before schema generation. A string names a root
  field or an entire source group. A pair `(source, field_name)` selects a field
  inside that group; `(None, field_name)` explicitly selects a root field. Names
  are Python parameter names, or the `SchemaField.field_name` returned by a hook,
  **before backend aliases**. Unknown names have no effect. An empty group is
  removed; remaining groups infer requiredness from their remaining fields.
  Excluding every input produces an empty object schema.
* `embed=False` leaves the input object intact. With `True`, exactly one remaining
  root property is unwrapped. This removes only one level: a sole `headers` group
  becomes an object of header fields, not the group's sole value. Zero or multiple
  root properties are not unwrapped. Definitions required by the result remain
  attached, including when reference resolution is disabled. References to the
  original input root or its properties keep their original targets after embedding.
* `resolve_refs=False` preserves native references. With `True`, local acyclic
  references are inlined; recursive references and discriminator targets retain
  their definitions. Constraints beside a reference are preserved using `allOf`.
  External references are never fetched; references crossing a nested `$id`
  boundary retain their scope and remain references. Definitions are retained
  conservatively when URI or anchor references may target an embedded resource.
  Defaults, examples, enum members and constants are data and are not traversed
  as schemas.

These options affect documentation only; they do not change validation or
execution. Processing does not mutate the backend's cached schema or later calls.
`get_response_schema()` keeps its original API and native reference layout.

The existing `fast_depends.pydantic.schema.get_schema()` helper shares embedding
and reference processing. It still selects Pydantic, works without a runtime
serializer, excludes by Python name, ignores custom field hooks, and returns
`{"title": ..., "type": "null"}` when no inputs remain.

## Describing custom fields

Override `CustomField.get_schema(parameter: OptionItem) -> SchemaField | None`
to describe an external input. The default implementation returns `None`, which
hides the field. Existing custom fields therefore keep their previous behavior.
The hook is synchronous and should only describe the input; it must not fetch
values or execute application code.

```python
from typing import Annotated, Any

from fast_depends import Provider
from fast_depends.core import build_call_model
from fast_depends.library import CustomField, SchemaField
from fast_depends.library.serializer import OptionItem
from fast_depends.pydantic import PydanticSerializer


class Header(CustomField):
    def get_schema(self, parameter: OptionItem) -> SchemaField:
        return SchemaField(
            field_name=parameter.field_name,
            field_type=parameter.field_type,
            default_value=parameter.default_value,
            source="headers",
        )

    def use(self, **kwargs: Any) -> dict[str, Any]:
        kwargs = super().use(**kwargs)
        headers = kwargs.get("headers", {})
        if self.param_name in headers:
            kwargs[self.param_name] = headers[self.param_name]
        return kwargs


def handler(token: Annotated[str, Header(cast=False)]):
    return token


call = build_call_model(
    handler,
    dependency_provider=Provider(),
    serializer_cls=PydanticSerializer(),
)
assert call.serializer is not None
schema = call.serializer.get_schema()
```

The hook's `parameter` contains the Python name, declared type, default and
parameter kind before the runtime transformations for `cast=False` or
`required=False`. An unannotated parameter has type `Any`. The `CustomField`
marker is removed from `Annotated`, while other metadata, including backend
constraints, is retained. A missing default or a `CustomField` used as the
default is represented by `Ellipsis`. `parameter.source` is the custom field
instance. These descriptions are also available in nested and extra dependencies,
including active provider overrides, even if a dependency has no serializer.

`SchemaField` uses the following contract:

| Argument | Meaning |
| --- | --- |
| `field_name` | Field name for the backend model; normally the Python parameter name. |
| `field_type` | External input type, including supported `Annotated` metadata. It may differ from the injected value's type. |
| `default_value=...` | `Ellipsis` for no default, a value, or a native backend field descriptor. |
| `source=None` | Place the field at the root. A non-empty string puts it inside the object named by that source. |
| `required=None` | Let the backend infer requiredness from the type/default. With `CustomField(required=False)`, omit the field from `required`. Explicit `True` or `False` overrides this inference. |

An optional input need not accept `null`: `required=False` removes it from
`required` without adding `null` to its declared type or inventing a default.
Defaults and factories supplied to the hook remain native backend values.

Use backend metadata for aliases and constraints: for example,
`Field(..., alias="x-token", min_length=1)` with Pydantic, or
`msgspec.field(name="x-token")` and `Annotated[str, msgspec.Meta(min_length=1)]`
with Msgspec. The hook can return these in `default_value` and `field_type`.
Aliases (including Pydantic validation aliases and alias generators) are applied
within the field's source. They do not rename the source itself.

For the example above, the schema describes this shape (native `$ref` and
definitions may represent the nested object):

```json
{
  "type": "object",
  "properties": {
    "headers": {
      "type": "object",
      "properties": {"token": {"type": "string"}},
      "required": ["token"]
    }
  },
  "required": ["headers"]
}
```

Sources are arbitrary names, not transport classes or a fixed list. `headers`,
`path`, `query`, and application-defined names all use the same object grouping.
A group is required at the root if any of its fields is required. A group with
only optional fields can be omitted. Ordinary parameters remain at the root.

The same name in different sources is retained separately. Within a source,
duplicate custom input names or aliases raise `ValueError`, as do collisions
between a root input and a source name. Custom descriptions do not use ordinary
parameters' first-occurrence rule. A dependency model reached through multiple
paths is described once; different dependencies describing the same name in the
same source are considered a conflict. Unsupported field names and metadata
remain subject to the chosen backend's restrictions.

Grouping is a schema representation. Runtime extraction remains the custom
field's responsibility. Getting a schema does not change `cast`, `required`,
argument validation, response schemas, or the existing serializer. Standalone
serializers continue to describe their configured options without calling hooks.
The legacy Pydantic schema helper does not use this hook.
