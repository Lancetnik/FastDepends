import pytest

from fast_depends.pydantic._compat import PYDANTIC_V2

pydanticV1 = pytest.mark.skipif(PYDANTIC_V2, reason="requires PydanticV2")  # noqa: N816

pydanticV2 = pytest.mark.skipif(not PYDANTIC_V2, reason="requires PydanticV1")  # noqa: N816
