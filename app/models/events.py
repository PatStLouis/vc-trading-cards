from pydantic import BaseModel, Field
from typing import List, Union, Literal

class NewSetEvent(BaseModel):
    setName: str = Field()
    members: str = Field()

class DropEvent(BaseModel):
    setName: str = Field()
    quantity: int = Field()

class DrawEvent(BaseModel):
    username: str = Field()
    quantity: int = Field()
    cards: List[str] = Field()

class TradeEvent(BaseModel):
    cardId: str = Field()
    toUser: str = Field()
    fromUser: str = Field()

class Event(BaseModel):
    type: str = Field()
    timestamp: str = Field()
    event: Union[DropEvent, DrawEvent, TradeEvent] = Field()