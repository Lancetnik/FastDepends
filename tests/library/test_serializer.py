from typing import Any

from fast_depends import Depends, Provider, inject
from fast_depends.library.serializer import OptionItem, Serializer, SerializerProto


class EchoSerializer(Serializer):
    """The smallest possible `Serializer`: everything else is inherited."""

    def __call__(self, call_kwargs: dict[str, Any]) -> dict[str, Any]:
        return call_kwargs


class EchoSerializerFactory(SerializerProto):
    def __call__(
        self,
        *,
        name: str,
        options: list[OptionItem],
        response_type: Any,
    ) -> EchoSerializer:
        return EchoSerializer(
            name=name,
            options=options,
            response_type=response_type,
        )


def test_default_encode_uses_stdlib_json() -> None:
    assert EchoSerializerFactory.encode({"a": 1}) == b'{"a": 1}'


def test_default_get_aliases_is_empty() -> None:
    serializer = EchoSerializer(name="func", options=[], response_type=None)
    assert serializer.get_aliases() == ()


def test_minimal_serializer_is_usable() -> None:
    def dep() -> int:
        return 1

    @inject(
        serializer_cls=EchoSerializerFactory(),
        dependency_provider=Provider(),
        cast_result=True,
    )
    def func(a: int, *, b: str = "b", d: int = Depends(dep)) -> str:
        return f"{a}-{b}-{d}"

    # nothing is casted - the serializer echoes its input back
    assert func("1") == "1-b-1"
