from fast_depends.library import CustomField, SchemaField
from tests.serializers.test_schema import resolve_root


class Input(CustomField):
    def __init__(self, source=None, name=None, **kwargs):
        super().__init__(**kwargs)
        self.source = source
        self.name = name

    def get_schema(self, parameter):
        return SchemaField(
            field_name=self.name or parameter.field_name,
            field_type=parameter.field_type,
            default_value=parameter.default_value,
            source=self.source,
        )

    def use(self, **kwargs):
        values = kwargs if self.source is None else kwargs.get(self.source, {})
        name = self.name or self.param_name
        if name in values:
            kwargs[self.param_name] = values[name]
        return kwargs


def source_schema(schema, source):
    value = resolve_root(schema)["properties"][source]
    return resolve_root({**schema, **value}) if "$ref" in value else value
