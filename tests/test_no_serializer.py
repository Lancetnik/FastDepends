from fast_depends import inject


def test_generator():
    @inject(serializer_cls=None)
    def simple_func(a: str) -> str:
        for _ in range(2):
            yield a

    for i in simple_func(1):
        assert i == 1
