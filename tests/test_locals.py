from __future__ import annotations

from fast_depends import inject
from tests.marks import pydantic

try:
    from pydantic import BaseModel
except ImportError:
    pass


def wrap(func):
    return inject(func)


@pydantic
def test_localns():
    class M(BaseModel):
        a: str

    @wrap
    def m(a: M) -> M:
        return a

    m(a={"a": "Hi!"})
