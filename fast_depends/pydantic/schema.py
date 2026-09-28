from collections.abc import Iterable
from inspect import Parameter
from typing import Any

from fast_depends.core import CallModel
from fast_depends.pydantic._compat import PYDANTIC_V2
from fast_depends.pydantic.serializer import PydanticSerializer


def get_schema(
    call: CallModel,
    *,
    embed: bool = False,
    resolve_refs: bool = False,
    exclude: Iterable[str] = (),
) -> dict[str, Any]:
    excluded = set(exclude)
    options = [i for i in call.flat_params if i.field_name not in excluded]

    name = getattr(call.serializer, "name", "Undefined")

    if not options:
        return {"title": name, "type": "null"}

    serializer = PydanticSerializer()(
        name=name,
        options=options,
        response_type=Parameter.empty,
    )
    body = serializer.get_schema()

    if resolve_refs:
        pydantic_key = "$defs" if PYDANTIC_V2 else "definitions"
        body = _move_pydantic_refs(body, pydantic_key)
        body.pop(pydantic_key, None)

    if embed and len(body["properties"]) == 1:
        body = list(body["properties"].values())[0]

    return body


def _move_pydantic_refs(
    original: Any, key: str, refs: dict[str, Any] | None = None
) -> Any:
    if not isinstance(original, dict):
        return original

    data = original.copy()

    if refs is None:
        raw_refs = data.get(key, {})
        refs = _move_pydantic_refs(raw_refs, key, raw_refs)

    name: str | None = None
    for k in data:
        if k == "$ref":
            name = data[k].replace(f"#/{key}/", "")

        elif isinstance(data[k], dict):
            data[k] = _move_pydantic_refs(data[k], key, refs)

        elif isinstance(data[k], list):
            for i in range(len(data[k])):
                data[k][i] = _move_pydantic_refs(data[k][i], key, refs)

    if name:
        assert refs, "Smth wrong"
        data = refs[name]

    return data
