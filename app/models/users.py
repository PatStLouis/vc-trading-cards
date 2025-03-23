from pydantic import BaseModel, Field
from typing import List, Union, Literal

class User(BaseModel):
    username: str = Field()
    cards: List[str] = Field([])