from __future__ import annotations

from pydantic import BaseModel

from fast_depends import inject


def test_localns():
    class M(BaseModel):
        a: str

    @inject
    def m(a: M) -> M:
        return a

    m(a={"a": "Hi!"})
