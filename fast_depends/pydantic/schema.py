from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from fast_depends.library.schema_processing import SchemaExclude

if TYPE_CHECKING:
    from fast_depends.core import CallModel


def get_schema(
    call: "CallModel",
    *,
    embed: bool = False,
    resolve_refs: bool = False,
    exclude: Iterable[SchemaExclude] = (),
) -> dict[str, Any]:
    """Describe external inputs using the call's configured serializer.

    Calls without a serializer cannot generate a schema. Custom serializers
    may leave schema generation unimplemented.
    """
    if call.serializer is None:
        raise ValueError("Schema generation requires a call with a configured serializer")
    return call.serializer.get_schema(
        embed=embed, resolve_refs=resolve_refs, exclude=exclude
    )
