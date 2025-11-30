import pytest

try:
    from fast_depends.pydantic._compat import PYDANTIC_V2

    HAS_PYDANTIC = True

except ImportError:
    HAS_PYDANTIC = False
    PYDANTIC_V2 = False

try:
    from fast_depends.msgspec import MsgSpecSerializer  # noqa: F401

    HAS_MSGSPEC = True
except ImportError:
    HAS_MSGSPEC = False


serializer = pytest.mark.skipif(
    not HAS_MSGSPEC and not HAS_PYDANTIC, reason="requires serializer"
)  # noqa: N816

msgspec = pytest.mark.skipif(not HAS_MSGSPEC, reason="requires Msgspec")  # noqa: N816

pydantic = pytest.mark.skipif(not HAS_PYDANTIC, reason="requires Pydantic")  # noqa: N816

pydanticV1 = pytest.mark.skipif(
    not HAS_PYDANTIC or PYDANTIC_V2, reason="requires PydanticV1"
)  # noqa: N816

pydanticV2 = pytest.mark.skipif(
    not HAS_PYDANTIC or not PYDANTIC_V2, reason="requires PydanticV2"
)  # noqa: N816
