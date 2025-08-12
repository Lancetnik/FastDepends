# Is that FastAPI???
from pydantic import Field
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from fast_depends import Depends, inject


def unwrap_path(func):
    async def wrapper(request):  # unwrap incoming params to **kwargs here
        return await func(**request.path_params)
    return wrapper

async def get_user(user_id: int = Field(..., alias="id")):
    return f"user {user_id}"

@unwrap_path
@inject  # cast incoming kwargs here
async def hello(user: str = Depends(get_user)):
    return PlainTextResponse(f"Hello, {user}!")

app = Starlette(debug=True, routes=[
    Route("/{id}", hello)
])
