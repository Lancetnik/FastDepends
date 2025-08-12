from flask import Flask
from pydantic import Field

from fast_depends import Depends, inject

app = Flask(__name__)

def get_user(user_id: int = Field(..., alias="id")):
    return f"user {user_id}"

@app.get("/<id>")
@inject
def hello(user: str = Depends(get_user)):
    return f"<p>Hello, {user}!</p>"
