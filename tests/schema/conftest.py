from functools import partial

import pytest

from fast_depends import inject
from fast_depends.core import CallModel
from fast_depends.library.serializer import Serializer, SerializerProto


class CallCapture:
    model: CallModel

    def __call__(self, model: CallModel) -> CallModel:
        self.model = model
        return model

    @property
    def serializer(self) -> Serializer:
        assert self.model.serializer is not None
        return self.model.serializer


@pytest.fixture
def capture() -> CallCapture:
    return CallCapture()


@pytest.fixture(params=("pydantic", "msgspec"))
def serializer_factory(request: pytest.FixtureRequest) -> SerializerProto:
    pytest.importorskip(request.param)
    if request.param == "pydantic":
        from fast_depends.pydantic import PydanticSerializer

        return PydanticSerializer()

    from fast_depends.msgspec import MsgSpecSerializer

    return MsgSpecSerializer()


@pytest.fixture
def schema_inject(serializer_factory, provider, capture):
    return partial(
        inject,
        serializer_cls=serializer_factory,
        dependency_provider=provider,
        wrap_model=capture,
    )
