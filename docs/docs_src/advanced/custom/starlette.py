from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from fast_depends import inject
from fast_depends.library import CustomField

class Path(CustomField):
    def use(self, /, *, request, **kwargs):
        return {
            **super().use(request=request, **kwargs),
            self.param_name: request.path_params.get(self.param_name)
        }

def wrap_starlette(func):
    async def wrapper(request):
        return await inject(func)(
            request=request
        )
    return wrapper

@wrap_starlette
async def hello(user: str = Path()):
    return PlainTextResponse(f"Hello, {user}!")

app = Starlette(debug=True, routes=[
    Route("/{user}", hello)
])
