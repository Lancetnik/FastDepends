from typing_extensions import Annotated
from fast_depends import Depends
from pydantic import Field

CurrentUser = Annotated[User, Depends(get_user)]
MaxLenField = Annotated[str, Field(..., max_length="32")]