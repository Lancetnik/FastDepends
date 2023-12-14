import pytest

from fast_depends import Depends, inject


def _get_var():
    return 1


class Class:
    @inject
    def __init__(self, a=Depends(_get_var)) -> None:
        self.a = a

    @inject
    async def calc(self, a=Depends(_get_var)) -> int:
        return a + self.a


@pytest.mark.anyio
async def test_class():
    assert await Class().calc() == 2
