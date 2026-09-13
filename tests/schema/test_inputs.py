from typing import Annotated, Any
from unittest.mock import Mock

from dirty_equals import IsPartialDict

from fast_depends import Depends
from fast_depends.library import CustomField
from tests.serializers.test_schema import resolve_root


def test_dependency_inputs(schema_inject, capture):
    def dependency(count: int): ...

    @schema_inject
    def handler(name: str, result: Annotated[Any, Depends(dependency)]): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={
            "name": IsPartialDict(type="string"),
            "count": IsPartialDict(type="integer"),
        }
    )


def test_dependency_required_input(schema_inject, capture):
    def dependency(count: int): ...

    @schema_inject
    def handler(result: Any = Depends(dependency)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        required=["count"]
    )


def test_dependency_default(schema_inject, capture):
    def dependency(count: int = 10): ...

    @schema_inject
    def handler(result: Any = Depends(dependency)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"count": IsPartialDict(default=10)}
    )


def test_dependency_default_is_optional(schema_inject, capture):
    def dependency(count: int = 10): ...

    @schema_inject
    def handler(result: Any = Depends(dependency)): ...

    assert not resolve_root(capture.serializer.get_schema()).get("required")


def test_nested_dependency_inputs(schema_inject, capture):
    def nested(token: str): ...

    def dependency(value: Any = Depends(nested)): ...

    @schema_inject
    def handler(result: Any = Depends(dependency)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"token": IsPartialDict(type="string")}
    )


def test_extra_dependency_inputs(schema_inject, capture):
    def extra(enabled: bool): ...

    @schema_inject(extra_dependencies=(Depends(extra),))
    def handler(): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"enabled": IsPartialDict(type="boolean")}
    )


def test_nested_extra_dependency_inputs(schema_inject, capture):
    def nested(token: str): ...

    def extra(value: Any = Depends(nested)): ...

    @schema_inject(extra_dependencies=(Depends(extra),))
    def handler(): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"token": IsPartialDict(type="string")}
    )


def test_own_parameter_precedes_dependency(schema_inject, capture):
    def dependency(shared: str): ...

    @schema_inject
    def handler(shared: int, value: Any = Depends(dependency)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"shared": IsPartialDict(type="integer")}
    )


def test_first_dependency_parameter_wins(schema_inject, capture):
    def first(shared: str): ...

    def second(shared: float): ...

    @schema_inject
    def handler(a: Any = Depends(first), b: Any = Depends(second)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"shared": IsPartialDict(type="string")}
    )


def test_nested_dependency_precedes_next_dependency(schema_inject, capture):
    def nested(shared: str): ...

    def first(value: Any = Depends(nested)): ...

    def second(shared: int): ...

    @schema_inject
    def handler(a: Any = Depends(first), b: Any = Depends(second)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"shared": IsPartialDict(type="string")}
    )


def test_dependency_precedes_extra_dependency(schema_inject, capture):
    def dependency(shared: str): ...

    def extra(shared: bool): ...

    @schema_inject(extra_dependencies=(Depends(extra),))
    def handler(value: Any = Depends(dependency)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"shared": IsPartialDict(type="string")}
    )


def test_empty_external_inputs(schema_inject, capture):
    def dependency(): ...

    @schema_inject
    def handler(value: Any = Depends(dependency)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        type="object", properties={}
    )


def test_custom_fields_are_excluded(schema_inject, capture):
    @schema_inject
    def handler(name: str, context: Annotated[str, CustomField()]): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"name": IsPartialDict(type="string")}
    )


def test_custom_fields_in_dependencies_are_excluded(schema_inject, capture):
    def dependency(name: str, context: Annotated[str, CustomField()]): ...

    @schema_inject
    def handler(value: Any = Depends(dependency)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"name": IsPartialDict(type="string")}
    )


def test_unsupported_injected_type_is_excluded(schema_inject, capture):
    class Context:
        pass

    def dependency(name: str): ...

    @schema_inject
    def handler(context: Context = Depends(dependency)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"name": IsPartialDict(type="string")}
    )


def test_uncast_dependency_still_describes_inputs(schema_inject, capture):
    def dependency(count: int): ...

    @schema_inject
    def handler(value: int = Depends(dependency, cast=False)): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(
        properties={"count": IsPartialDict(type="integer")}
    )


def test_schema_does_not_execute_handler(schema_inject, capture):
    called = Mock()

    @schema_inject
    def handler(name: str):
        called()

    capture.serializer.get_schema()

    called.assert_not_called()


def test_schema_does_not_execute_dependency(schema_inject, capture):
    called = Mock()

    def dependency(count: int):
        called()

    @schema_inject
    def handler(value: Any = Depends(dependency)): ...

    capture.serializer.get_schema()

    called.assert_not_called()


def test_schema_does_not_execute_extra_dependency(schema_inject, capture):
    called = Mock()

    def extra(token: str):
        called()

    @schema_inject(extra_dependencies=(Depends(extra),))
    def handler(): ...

    capture.serializer.get_schema()

    called.assert_not_called()


def test_schema_does_not_execute_custom_field(schema_inject, capture):
    class Context(CustomField):
        def use(self, **kwargs):
            raise AssertionError("Schema generation executed a custom field")

    @schema_inject
    def handler(context: Annotated[str, Context()]): ...

    assert resolve_root(capture.serializer.get_schema()) == IsPartialDict(properties={})
