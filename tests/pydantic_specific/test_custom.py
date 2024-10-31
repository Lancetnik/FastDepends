from typing import Annotated, Any

import pytest
from annotated_types import Ge

from fast_depends import inject
from fast_depends.exceptions import ValidationError
from fast_depends.library import CustomField
from tests.marks import pydanticV2


class Header(CustomField):
    def use(self, /, **kwargs: Any) -> dict[str, Any]:
        kwargs = super().use(**kwargs)
        if v := kwargs.get("headers", {}).get(self.param_name):
            kwargs[self.param_name] = v
        return kwargs


@pydanticV2
def test_annotated_header_with_meta():
    @inject
    def sync_catch(key: Annotated[int, Header(), Ge(3)] = 3):  # noqa: B008
        return key

    assert sync_catch(headers={"key": "4"}) == 4

    assert sync_catch(headers={}) == 3

    with pytest.raises(ValidationError):
        sync_catch(headers={"key": "2"})
