import pytest

try:
    from fast_depends.pydantic import PydanticSerializer  # noqa: F401

    HAS_PYDANTIC = True

except ImportError:
    HAS_PYDANTIC = False

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
