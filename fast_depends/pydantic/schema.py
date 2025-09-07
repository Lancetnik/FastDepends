from typing import Any, Optional

from fast_depends.core import CallModel
from fast_depends.pydantic._compat import PYDANTIC_V2, create_model, model_schema


def get_schema(
    call: CallModel,
    embed: bool = False,
    resolve_refs: bool = False,
) -> dict[str, Any]:
    class_options: dict[str, Any] = {
        i.field_name: (i.field_type, i.default_value)
        for i in call.flat_params
    }

    name = getattr(call.serializer, "name", "Undefined")

    if not class_options:
        return {"title": name, "type": "null"}

    params_model = create_model(
        name,
        **class_options
    )

    body = model_schema(params_model)

    if resolve_refs:
        pydantic_key = "$defs" if PYDANTIC_V2 else "definitions"
        body = _move_pydantic_refs(body, pydantic_key)
        body.pop(pydantic_key, None)

    if embed and len(body["properties"]) == 1:
        body = list(body["properties"].values())[0]

    return body


def _move_pydantic_refs(
    original: Any,
    key: str,
    refs: Optional[dict[str, Any]] = None
) -> Any:
    if not isinstance(original, dict):
        return original

    data = original.copy()

    if refs is None:
        raw_refs = data.get(key, {})
        refs = _move_pydantic_refs(raw_refs, key, raw_refs)

    name: Optional[str] = None
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
