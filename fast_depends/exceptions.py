from collections.abc import Sequence
from typing import Any

from fast_depends.library.serializer import OptionItem


class FastDependsError(Exception):
    pass


class ValidationError(ValueError, FastDependsError):
    def __init__(
        self,
        *,
        incoming_options: Any,
        locations: Sequence[Any],
        expected: dict[str, OptionItem],
        original_error: Exception,
    ) -> None:
        self.original_error = original_error
        self.incoming_options = incoming_options

        self.error_fields: tuple[OptionItem, ...] = tuple(
            expected[x] for x in locations if x in expected
        )
        if not self.error_fields:
            self.error_fields = tuple(expected.values())

        super().__init__()

    def __str__(self) -> str:
        if isinstance(self.incoming_options, dict):
            content = ", ".join(f"{k}=`{v}`" for k, v in self.incoming_options.items())
        else:
            content = f"`{self.incoming_options}`"

        return (
            "\n    Incoming options: "
            + content
            + "\n    In the following option types error occured:\n    "
            + "\n    ".join(map(str, self.error_fields))
        )
