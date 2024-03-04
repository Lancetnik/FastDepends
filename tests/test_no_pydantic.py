from typing import Dict, Tuple
from unittest.mock import MagicMock

from fast_depends import Depends, inject


def test_depends():
    def dep_func(b: int, a: int = 3):
        return a + b

    @inject
    def some_func(b: int, c=Depends(dep_func)) -> int:
        return b + c

    assert some_func(2) == 7


def test_args_kwargs_1():
    @inject(caster_cls=None)
    def simple_func(
        a: int,
        *args: Tuple[float, ...],
        b: int,
        **kwargs: Dict[str, int],
    ):
        return a, args, b, kwargs

    assert (
        1.0,
        (2.0, 3),
        3.0,
        {"key": 1.0},
    ) == simple_func(1.0, 2.0, 3, b=3.0, key=1.0)


def test_generator():
    mock = MagicMock()

    def func():
        mock.start()
        yield
        mock.end()

    @inject
    def simple_func(a: str, d=Depends(func)):
        for _ in range(2):
            yield a

    for i in simple_func("1"):
        mock.start.assert_called_once()
        assert not mock.end.called
        assert i == "1"

    mock.end.assert_called_once()
