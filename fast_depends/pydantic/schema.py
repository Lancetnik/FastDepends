from collections.abc import Iterable
from inspect import Parameter
from typing import Any

from fast_depends.core import CallModel
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
    return serializer.get_schema(embed=embed, resolve_refs=resolve_refs)
