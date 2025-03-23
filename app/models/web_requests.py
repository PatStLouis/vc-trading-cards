from pydantic import BaseModel, Field
from typing import List, Union, Literal, Dict
from app.static.samples import SAMPLE_SET, SAMPLE_DROP, SAMPLE_DRAW

class NewCardSet(BaseModel):
    label: str = Field(example=SAMPLE_SET['label'])
    entries: List[Dict[str, str]] = Field(example=SAMPLE_SET['entries'])

class NewCardBatch(BaseModel):
    set: str = Field(example=SAMPLE_DROP['setLabel'])
    size: int = Field(example=SAMPLE_DROP['quantity'])

class CardDraw(BaseModel):
    set: str = Field(example=SAMPLE_DRAW['setLabel'])
    quantity: int = Field(example=SAMPLE_DRAW['quantity'])
    username: str = Field(example=SAMPLE_DRAW['username'])

class CardTrade(BaseModel):
    cardId: str = Field()
    toUser: str = Field()
    fromUser: str = Field()