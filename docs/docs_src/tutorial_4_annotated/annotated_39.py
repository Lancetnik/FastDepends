from typing import Annotated
from pydantic import BaseModel, PositiveInt
from fast_depends import Depends, inject

class User(BaseModel):
    user_id: PositiveInt

def get_user(user: id) -> User:
    return User(user_id=user)

CurrentUser = Annotated[User, Depends(get_user)]

@inject
def do_smth_with_user(user: CurrentUser):
    ...

@inject
def do_another_smth_with_user(user: CurrentUser):
    ...
