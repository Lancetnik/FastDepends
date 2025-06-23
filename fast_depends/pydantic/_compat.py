import json
from typing import Any, Callable, Optional

from pydantic import BaseModel, create_model
from pydantic.version import VERSION as PYDANTIC_VERSION

__all__ = (
    "BaseModel",
    "create_model",
    "PYDANTIC_V2",
    "get_config_base",
    "ConfigDict",
    "TypeAdapter",
    "PydanticUserError",
)


json_dumps: Callable[..., bytes]
orjson: Any
ujson: Any

try:
    import orjson
except ImportError:
    orjson = None

try:
    import ujson
except ImportError:
    ujson = None

if orjson:
    json_loads = orjson.loads
    json_dumps = orjson.dumps

elif ujson:
    json_loads = ujson.loads

    def json_dumps(*a: Any, **kw: Any) -> bytes:
        return ujson.dumps(*a, **kw).encode()  # type: ignore[no-any-return]

else:
    json_loads = json.loads

    def json_dumps(*a: Any, **kw: Any) -> bytes:
        return json.dumps(*a, **kw).encode()

PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

default_pydantic_config = {"arbitrary_types_allowed": True}

# isort: off
if PYDANTIC_V2:
    from pydantic import ConfigDict, TypeAdapter
    from pydantic.fields import FieldInfo
    from pydantic.errors import PydanticUserError
    from pydantic_core import to_json as dump_json

    def model_schema(model: type[BaseModel]) -> dict[str, Any]:
        return model.model_json_schema()

    def get_config_base(config_data: Optional[ConfigDict] = None) -> ConfigDict:
        return config_data or ConfigDict(**default_pydantic_config)  # type: ignore[typeddict-item]

    def get_aliases(model: type[BaseModel]) -> tuple[str, ...]:
        return tuple(f.alias or name for name, f in get_model_fields(model).items())

    def get_model_fields(model: type[BaseModel]) -> dict[str, FieldInfo]:
        fields: Optional[dict[str, FieldInfo]] = getattr(
            model, "__pydantic_fields__", None
        )

        if fields is not None:
            return fields

        # Deprecated in Pydantic V2.11 to be removed in V3.0.
        return model.model_fields

else:
    from pydantic.config import get_config, ConfigDict, BaseConfig
    from pydantic.fields import ModelField
    from pydantic.json import pydantic_encoder

    TypeAdapter = None
    PydanticUserError = Exception

    def get_config_base(config_data: Optional[ConfigDict] = None) -> type[BaseConfig]:  # type: ignore[misc]
        return get_config(config_data or ConfigDict(**default_pydantic_config))  # type: ignore[typeddict-item]

    def model_schema(model: type[BaseModel]) -> dict[str, Any]:
        return model.schema()

    def get_aliases(model: type[BaseModel]) -> tuple[str, ...]:
        return tuple(f.alias or name for name, f in model.__fields__.items())

    def get_model_fields(model: type[BaseModel]) -> dict[str, ModelField]:
        return model.__fields__

    def dump_json(data: Any) -> bytes:
        return json_dumps(data, default=pydantic_encoder)
