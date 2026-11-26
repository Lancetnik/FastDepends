from collections.abc import Callable, Hashable, Sequence
from typing import Annotated, Any, get_args, get_origin

import msgspec

from fast_depends.library.serializer import InputField, OptionItem, PreparedValue


def _contract(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Annotated:
        base, *metadata = get_args(annotation)
        constraints = tuple(
            (
                "msgspec.Meta",
                item.gt,
                item.ge,
                item.lt,
                item.le,
                item.multiple_of,
                item.pattern,
                item.min_length,
                item.max_length,
                item.tz,
            )
            if isinstance(item, msgspec.Meta)
            else item
            for item in metadata
        )
        return (origin, _contract(base), constraints)
    if origin is not None:
        return (origin, tuple(_contract(item) for item in get_args(annotation)))
    return annotation


class SharedInputs:
    def __init__(
        self,
        name: str,
        fields: Sequence[InputField],
        dec_hook: Callable[[type, Any], Any] | None,
    ) -> None:
        self.dec_hook = dec_hook
        options: list[tuple[str, Any, Any]] = []
        bindings: list[tuple[str, Hashable]] = []
        for index, field in enumerate(fields):
            if len(field.paths) != 1 or len(field.paths[0]) != 1:
                raise TypeError("Msgspec shared inputs require a single field alias")
            alias = field.paths[0][0]
            if (
                not isinstance(alias, str)
                or not isinstance(field.contract, tuple)
                or not field.contract
                or field.contract[0] != "msgspec"
                or field.contract[2] is not dec_hook
            ):
                raise TypeError("Incompatible serializer for Msgspec shared inputs")
            default = (
                msgspec.field(name=alias)
                if field.required
                else msgspec.field(name=alias, default=msgspec.UNSET)
            )
            internal_name = f"input_{index}"
            options.append((internal_name, field.schema, default))
            bindings.append((internal_name, field.key))
        self.bindings = tuple(bindings)
        self.model = msgspec.defstruct(f"{name}Inputs", options, kw_only=True)
        msgspec.json.Decoder(self.model, dec_hook=dec_hook)

    def __call__(self, values: dict[str, Any]) -> dict[Hashable, PreparedValue]:
        if not self.bindings:
            return {}
        result = msgspec.convert(
            values,
            type=self.model,
            strict=False,
            str_keys=True,
            dec_hook=self.dec_hook,
        )
        return {
            key: PreparedValue(value)
            for name, key in self.bindings
            if (value := getattr(result, name)) is not msgspec.UNSET
        }


class NodePreparation:
    def __init__(
        self,
        name: str,
        options: dict[str, OptionItem],
        model: type[msgspec.Struct],
        dec_hook: Callable[[type, Any], Any] | None,
        aliases: dict[str, str],
    ) -> None:
        self.dec_hook = dec_hook
        self.fields: dict[str, InputField] = {}
        node_options: list[tuple[str, Any] | tuple[str, Any, Any]] = []
        for field in msgspec.structs.fields(model):
            option = options[field.name]
            alias = aliases[field.name]
            annotation = field.type
            if option.source is None:
                self.fields[field.name] = InputField(
                    option,
                    key=(option.source, alias),
                    paths=((alias,),),
                    required=field.required,
                    contract=("msgspec", _contract(annotation), dec_hook),
                    schema=annotation,
                    schema_option=OptionItem(
                        field.name,
                        annotation,
                        default_value=msgspec.field(name=alias),
                    ),
                )
                annotation = Any
            if field.default_factory is not msgspec.NODEFAULT:
                default = msgspec.field(default_factory=field.default_factory)
            elif field.default is not msgspec.NODEFAULT:
                default = field.default
            else:
                node_options.append((field.name, annotation))
                continue
            node_options.append((field.name, annotation, default))
        self.model: type[msgspec.Struct] | None = None
        self.model_name = f"{name}Resolved"
        self.model_options = node_options
        self.names = tuple(self.fields)
        self.direct = len(self.fields) == len(options)

    def prepare_resolved(self) -> type[msgspec.Struct]:
        if self.model is None:
            model = msgspec.defstruct(self.model_name, self.model_options, kw_only=True)
            msgspec.json.Decoder(model, dec_hook=self.dec_hook)
            self.model = model
            self.model_options = []
        return self.model

    def __call__(self, values: dict[str, Any]) -> dict[str, Any]:
        if self.direct and len(values) == len(self.names):
            unwrapped: dict[str, Any] = {}
            for name in self.names:
                value = values.get(name)
                if not isinstance(value, PreparedValue):
                    break
                unwrapped[name] = value.value
            else:
                return unwrapped
        supplied = values.copy()
        for name in self.names:
            if name not in supplied:
                continue
            value = supplied[name]
            if not isinstance(value, PreparedValue):
                raise TypeError(
                    f"External input {name!r} must be prepared before resolving arguments"
                )
            supplied[name] = value.value
        result = msgspec.convert(
            supplied,
            type=self.prepare_resolved(),
            strict=False,
            str_keys=True,
            dec_hook=self.dec_hook,
        )
        return {name: getattr(result, name) for name in result.__struct_fields__}
