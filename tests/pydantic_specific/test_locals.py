from __future__ import annotations

from pydantic import BaseModel

from fast_depends import inject


def wrap(func):
    return inject(func)


def test_localns():
    class M(BaseModel):
        a: str

    @wrap
    def m(a: M) -> M:
        return a

    m(a={"a": "Hi!"})
