from dataclasses import dataclass
from datetime import datetime, timezone

import pytest


@dataclass
class SimpleDataclass:
    r: str


now = datetime.now(timezone.utc)

parametrized = (
    pytest.param(
        "hello",
        b'"hello"',
        id="str",
    ),
    pytest.param(
        1.0,
        b"1.0",
        id="float",
    ),
    pytest.param(
        1,
        b"1",
        id="int",
    ),
    pytest.param(
        False,
        b"false",
        id="bool",
    ),
)

comptex_params = [
    pytest.param(
        {"m": 1},
        b'{"m":1}',
        id="dict",
    ),
    pytest.param(
        [1, 2, 3],
        b"[1,2,3]",
        id="list",
    ),
    pytest.param(
        SimpleDataclass(r="hello!"),
        b'{"r":"hello!"}',
        id="dataclass",
    ),
]
