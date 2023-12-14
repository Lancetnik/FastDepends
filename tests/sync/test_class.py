from fast_depends import Depends, inject


def _get_var():
    return 1


class Class:
    @inject
    def __init__(self, a=Depends(_get_var)) -> None:
        self.a = a

    @inject
    def calc(self, a=Depends(_get_var)) -> int:
        return a + self.a


def test_class():
    assert Class().calc() == 2
