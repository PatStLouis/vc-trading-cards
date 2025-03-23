from pydantic import BaseModel, Field
from typing import List, Union, Literal, Dict, Any
from enum import Enum

RARITY_VOLUMES = {
    'common': 50,
    'uncommon': 40,
    'rare': 25,
    'ultraRare': 10,
    'legendary': 5,
    'promo': None,
    'unique': 1,
}

class BaseModel(BaseModel):
    """Base model for all models in the application."""

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Dump the model to a dictionary."""
        return super().model_dump(by_alias=True, exclude_none=True, **kwargs)

class RarityEnum(str, Enum):
    common = 'common'
    uncommon = 'uncommon'
    rare = 'rare'
    ultraRare = 'ultraRare'
    legendary = 'legendary'
    promo = 'promo'
    unique = 'unique'

class CardEntry(BaseModel):
    name: str = Field()
    # holo: bool = Field(False)
    quote: str = Field()
    rarity: RarityEnum = Field()
    artwork: str = Field()
    photographer: str = Field()

class TradingCard(CardEntry):
    type: List[str] = Field(['TradingCard'])
    set: str = Field()
    # holo: bool = Field(False)
    number: str = Field()