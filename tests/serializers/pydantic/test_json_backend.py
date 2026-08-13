"""`fast_depends.pydantic._compat` picks its JSON backend at import time.

Which branch runs depends on what happens to be installed, so the module is
re-executed here against stubbed `sys.modules` entries instead. Coverage keys
line data off the file, so re-executing the real file from disk does measure
the real branches, and nothing is imported into the live module tree.
"""

import importlib.util
import json
import sys
from types import ModuleType

import pytest

import fast_depends.pydantic._compat as live_compat

BACKENDS = ("orjson", "ujson")


def make_backend(name: str) -> ModuleType:
    stub = ModuleType(name)
    stub.loads = json.loads  # type: ignore[attr-defined]
    stub.dumps = json.dumps  # type: ignore[attr-defined]
    return stub


def reload_compat(
    monkeypatch: pytest.MonkeyPatch,
    installed: dict[str, ModuleType],
) -> ModuleType:
    for name in BACKENDS:
        # a `None` entry makes the import fail the same way a missing
        # distribution would
        monkeypatch.setitem(sys.modules, name, installed.get(name))

    spec = importlib.util.spec_from_file_location(
        "fast_depends_compat_probe",
        live_compat.__file__,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_orjson_is_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    orjson, ujson = make_backend("orjson"), make_backend("ujson")

    compat = reload_compat(monkeypatch, {"orjson": orjson, "ujson": ujson})

    assert compat.orjson is orjson
    assert compat.ujson is ujson
    assert compat.json_loads is orjson.loads
    # orjson already returns `bytes`, so it is used as is
    assert compat.json_dumps is orjson.dumps


def test_ujson_is_used_without_orjson(monkeypatch: pytest.MonkeyPatch) -> None:
    ujson = make_backend("ujson")

    compat = reload_compat(monkeypatch, {"ujson": ujson})

    assert compat.orjson is None
    assert compat.json_loads is ujson.loads
    # ujson returns `str`, so the wrapper has to encode it
    assert compat.json_dumps({"a": 1}) == b'{"a": 1}'


def test_stdlib_json_is_the_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    compat = reload_compat(monkeypatch, {})

    assert compat.orjson is None
    assert compat.ujson is None
    assert compat.json_loads is json.loads
    assert compat.json_dumps({"a": 1}) == b'{"a": 1}'
