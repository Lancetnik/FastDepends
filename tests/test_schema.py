from typing import Optional

from pydantic import BaseModel, Field

from fast_depends import Depends
from fast_depends.core import build_call_model
from fast_depends.schema import get_schema


def test_base():
    def handler():
        pass

    schema = get_schema(build_call_model(handler))
    assert schema == {"title": "handler", "type": "null"}, schema


class TestNoType:
    def test_no_type(self):
        def handler(a):
            pass

        schema = get_schema(build_call_model(handler))
        assert schema == {
            "properties": {"a": {"title": "A"}},
            "required": ["a"],
            "title": "handler",
            "type": "object",
        }, schema

    def test_no_type_embeded(self):
        def handler(a):
            pass

        schema = get_schema(build_call_model(handler), embed=True)
        assert schema == {"title": "A"}, schema

    def test_no_type_with_default(self):
        def handler(a=None):
            pass

        schema = get_schema(build_call_model(handler))
        assert schema == {
            "properties": {"a": {"default": None, "title": "A"}},
            "title": "handler",
            "type": "object",
        }, schema

    def test_no_type_with_default_and_embed(self):
        def handler(a=None):
            pass

        schema = get_schema(build_call_model(handler), embed=True)
        assert schema == {"default": None, "title": "A"}, schema


class TestOneArg:
    def test_one_arg(self):
        def handler(a: int):
            pass

        schema = get_schema(build_call_model(handler))
        assert schema == {
            "properties": {"a": {"title": "A", "type": "integer"}},
            "required": ["a"],
            "title": "handler",
            "type": "object",
        }, schema

    def test_one_arg_with_embed(self):
        def handler(a: int):
            pass

        schema = get_schema(build_call_model(handler), embed=True)
        assert schema == {"title": "A", "type": "integer"}, schema

    def test_one_arg_with_optional(self):
        def handler(a: Optional[int]):
            pass

        schema = get_schema(build_call_model(handler))
        assert schema == {
            "properties": {
                "a": {"anyOf": [{"type": "integer"}, {"type": "null"}], "title": "A"}
            },
            "required": ["a"],
            "title": "handler",
            "type": "object",
        }, schema

    def test_one_arg_with_default(self):
        def handler(a: int = 0):
            pass

        schema = get_schema(build_call_model(handler))
        assert schema == {
            "properties": {"a": {"default": 0, "title": "A", "type": "integer"}},
            "title": "handler",
            "type": "object",
        }, schema

    def test_one_arg_with_default_and_embed(self):
        def handler(a: int = 0):
            pass

        schema = get_schema(build_call_model(handler), embed=True)
        assert schema == {"default": 0, "title": "A", "type": "integer"}, schema


class TestOneArgWithModel:
    def test_base(self):
        class Model(BaseModel):
            a: int

        def handler(a: Model):
            pass

        schema = get_schema(build_call_model(handler))
        assert schema == {
            "$defs": {
                "Model": {
                    "properties": {"a": {"title": "A", "type": "integer"}},
                    "required": ["a"],
                    "title": "Model",
                    "type": "object",
                }
            },
            "properties": {"a": {"$ref": "#/$defs/Model"}},
            "required": ["a"],
            "title": "handler",
            "type": "object",
        }, schema

    def test_resolved_model(self):
        class Model(BaseModel):
            a: int

        def handler(a: Model):
            pass

        schema = get_schema(build_call_model(handler), resolve_refs=True)
        assert schema == {
            "properties": {
                "a": {
                    "properties": {"a": {"title": "A", "type": "integer"}},
                    "required": ["a"],
                    "title": "Model",
                    "type": "object",
                }
            },
            "required": ["a"],
            "title": "handler",
            "type": "object",
        }, schema

    def test_optional_model(self):
        class Model(BaseModel):
            a: int

        def handler(a: Optional[Model] = None):
            pass

        schema = get_schema(build_call_model(handler), resolve_refs=True)
        assert schema == {
            "properties": {
                "a": {
                    "anyOf": [
                        {
                            "properties": {"a": {"title": "A", "type": "integer"}},
                            "required": ["a"],
                            "title": "Model",
                            "type": "object",
                        },
                        {"type": "null"},
                    ],
                    "default": None,
                }
            },
            "title": "handler",
            "type": "object",
        }, schema

    def test_optional_embeded_model(self):
        class Model(BaseModel):
            a: int

        def handler(a: Optional[Model]):
            pass

        schema = get_schema(build_call_model(handler), resolve_refs=True, embed=True)
        assert schema == {
            "anyOf": [
                {
                    "properties": {"a": {"title": "A", "type": "integer"}},
                    "required": ["a"],
                    "title": "Model",
                    "type": "object",
                },
                {"type": "null"},
            ]
        }, schema

    def test_nested_resolved_model(self):
        class Model2(BaseModel):
            a: int

        class Model(BaseModel):
            a: Model2

        def handler(a: Model):
            pass

        schema = get_schema(build_call_model(handler), resolve_refs=True)
        assert schema == {
            "properties": {
                "a": {
                    "properties": {
                        "a": {
                            "properties": {"a": {"title": "A", "type": "integer"}},
                            "required": ["a"],
                            "title": "Model2",
                            "type": "object",
                        }
                    },
                    "required": ["a"],
                    "title": "Model",
                    "type": "object",
                }
            },
            "required": ["a"],
            "title": "handler",
            "type": "object",
        }, schema

    def test_embeded_model(self):
        class Model(BaseModel):
            a: int

        def handler(a: Model):
            pass

        schema = get_schema(build_call_model(handler), resolve_refs=True, embed=True)
        assert schema == {
            "properties": {"a": {"title": "A", "type": "integer"}},
            "required": ["a"],
            "title": "Model",
            "type": "object",
        }, schema

    def test_embeded_resolved_model(self):
        class Model2(BaseModel):
            a: int

        class Model(BaseModel):
            a: Model2

        def handler(a: Model):
            pass

        schema = get_schema(build_call_model(handler), resolve_refs=True, embed=True)
        assert schema == {
            "properties": {
                "a": {
                    "properties": {"a": {"title": "A", "type": "integer"}},
                    "required": ["a"],
                    "title": "Model2",
                    "type": "object",
                }
            },
            "required": ["a"],
            "title": "Model",
            "type": "object",
        }, schema


class TestMultiArgs:
    def test_base(self):
        def handler(a, b):
            pass

        schema = get_schema(build_call_model(handler))
        assert schema == {
            "properties": {"a": {"title": "A"}, "b": {"title": "B"}},
            "required": ["a", "b"],
            "title": "handler",
            "type": "object",
        }, schema

    def test_types_and_default(self):
        def handler(a: str, b: int = 0):
            pass

        schema = get_schema(build_call_model(handler))
        assert schema == {
            "properties": {
                "a": {"title": "A", "type": "string"},
                "b": {"default": 0, "title": "B", "type": "integer"},
            },
            "required": ["a"],
            "title": "handler",
            "type": "object",
        }, schema

    def test_ignores_embed(self):
        def handler(a: str, b: int = 0):
            pass

        schema = get_schema(build_call_model(handler), embed=True)
        assert schema == {
            "properties": {
                "a": {"title": "A", "type": "string"},
                "b": {"default": 0, "title": "B", "type": "integer"},
            },
            "required": ["a"],
            "title": "handler",
            "type": "object",
        }, schema

    def test_model(self):
        class Model(BaseModel):
            a: int = Field(0, description="description")

        def handler(a: str, b: Model):
            pass

        schema = get_schema(build_call_model(handler))
        assert schema == {
            "$defs": {
                "Model": {
                    "properties": {
                        "a": {
                            "default": 0,
                            "description": "description",
                            "title": "A",
                            "type": "integer",
                        }
                    },
                    "title": "Model",
                    "type": "object",
                }
            },
            "properties": {
                "a": {"title": "A", "type": "string"},
                "b": {"$ref": "#/$defs/Model"},
            },
            "required": ["a", "b"],
            "title": "handler",
            "type": "object",
        }, schema

    def test_resolved_model(self):
        class Model(BaseModel):
            a: int = Field(0, description="description")

        def handler(a: str, b: Model):
            pass

        schema = get_schema(build_call_model(handler), resolve_refs=True)
        assert schema == {
            "properties": {
                "a": {"title": "A", "type": "string"},
                "b": {
                    "properties": {
                        "a": {
                            "default": 0,
                            "description": "description",
                            "title": "A",
                            "type": "integer",
                        }
                    },
                    "title": "Model",
                    "type": "object",
                },
            },
            "required": ["a", "b"],
            "title": "handler",
            "type": "object",
        }, schema


def test_depends():
    class Model(BaseModel):
        a: int = Field(0, description="description")

    class CustomClass:
        pass

    def dep4(d: Model):
        ...

    def dep2(c: float = Field(..., title="best")):
        ...

    def dep(a: float = 1, d: CustomClass = Depends(dep2)):
        ...

    def handler(
        b: str = Field(""),
        a=Depends(dep),
    ):
        ...

    schema = get_schema(
        build_call_model(handler, extra_dependencies=(Depends(dep4),)),
        resolve_refs=True,
        embed=True,
    )

    assert schema == {
        "properties": {
            "a": {"default": 1, "title": "A", "type": "number"},
            "b": {"default": "", "title": "B", "type": "string"},
            "c": {"title": "best", "type": "number"},
            "d": {
                "properties": {
                    "a": {
                        "default": 0,
                        "description": "description",
                        "title": "A",
                        "type": "integer",
                    }
                },
                "title": "Model",
                "type": "object",
            },
        },
        "required": ["c", "d"],
        "title": "handler",
        "type": "object",
    }, schema
