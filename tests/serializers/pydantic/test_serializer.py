from fast_depends import Provider, inject
from fast_depends.pydantic import PydanticSerializer


def test_non_class_response_type() -> None:
    """`issubclass()` raises for non-class annotations such as unions.

    The serializer has to fall back to a `TypeAdapter` instead of treating the
    annotation as a model.
    """

    @inject(
        serializer_cls=PydanticSerializer(),
        dependency_provider=Provider(),
        cast_result=True,
    )
    def func(a: int) -> int | None:
        return a

    assert func("1") == 1
