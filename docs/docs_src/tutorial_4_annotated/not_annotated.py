from fast_depends import Depends, inject
from pydantic import BaseModel, PositiveInt

class User(BaseModel):
    user_id: PositiveInt

def get_user(user: id) -> User:
    return User(user_id=user)

@inject
def do_smth_with_user(user: User = Depends(get_user)):
    ...

@inject
def do_another_smth_with_user(user: User = Depends(get_user)):
    ...