from flask import Flask
from fast_depends import inject, Depends
from pydantic import Field

app = Flask(__name__)

def get_user(user_id: int = Field(..., alias="id")):
    return f"user {user_id}"

@app.get("/<id>")
@inject
def hello(user: str = Depends(get_user)):
    return f"<p>Hello, {user}!</p>"