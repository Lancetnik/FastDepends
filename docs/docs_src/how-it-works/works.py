from pydantic import BaseModel

from fast_depends import Depends


def simple_dependency(a: int, **kwargs):
    return a

def my_function(a: int, b: int, d = Depends(simple_dependency)) -> float:
    return a + b + d

# Declare function representation model
class MyFunctionRepresentation(BaseModel):
    a: int
    b: int

args, kwargs = (), {"a": 1, "b": "3"}

# Cast incomint arguments
arguments_model = MyFunctionRepresentation(**kwargs)

# Use them
new_kwargs = arguments_model.dict()
base_response = my_function(
    **new_kwargs,
    d=simple_dependency(**new_kwargs)
)

class ResponseModel(BaseModel):
    field: float

# Cast response
real_response = ResponseModel(field=base_response).field
