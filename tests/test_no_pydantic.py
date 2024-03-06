from fast_depends import inject
from tests.marks import no_pydantic


@no_pydantic
def test_generator():
    @inject
    def simple_func(a: str) -> str:
        for _ in range(2):
            yield a

    for i in simple_func(1):
        assert i == 1
