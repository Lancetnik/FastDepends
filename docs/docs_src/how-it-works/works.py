from pydantic import BaseModel

def my_function(a: int, b: int) -> float:
    return a + b

# Declare function representation model
class MyFunctionRepresentation(BaseModel):
    a: int
    b: int

args, kwargs = (), {"a": 1, "b": "3"}

# Cast incomint arguments
arguments_model = MyFunctionRepresentation(**kwargs)

# Use them
base_response = my_function(**arguments_model.dict())

class ResponseModel(BaseModel):
    field: float

# Cast response
real_response = ResponseModel(field=base_response).field