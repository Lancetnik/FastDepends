from typing import Annotated

from pydantic import Field

from fast_depends import Depends

CurrentUser = Annotated[User, Depends(get_user)]
MaxLenField = Annotated[str, Field(..., max_length="32")]
