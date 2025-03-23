from pydantic import BaseModel, Field, computed_field, model_serializer
from typing import List, Dict, Union, Literal, Any
from .cards import TradingCard

from config import settings


class BaseModel(BaseModel):
    """Base model for all models in the application."""

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Dump the model to a dictionary."""
        return super().model_dump(by_alias=True, exclude_none=True, **kwargs)

class Issuer(BaseModel):
    id: str = Field(settings.ISSUER_ID)
    name: str = Field(settings.ISSUER_NAME)
    image: str = Field(settings.ISSUER_IMAGE)

class DataIntegrityProof(BaseModel):
    type: str = Field('DataIntegrityProof')
    cryptosuite: str = Field('eddsa-jcs-2022')
    proofPurpose: str = Field('assertionMethod')
    verificationMethod: str = Field()
    proofValue: str = Field()

class Credential(BaseModel):
    context: List[str] = Field(
        [
            'https://www.w3.org/ns/credentials/v2',
            'https://www.w3.org/ns/credentials/examples/v2'
        ],
        alias='@context'
    )
    type: List[str] = Field(['VerifiableCredential', 'VerifiableTradingCard'])
    id: str = Field()
    name: str = Field(settings.CRED_NAME)
    description: str = Field(settings.CRED_DESC)
    issuer: Issuer = Field(Issuer())
    validFrom: str = Field()
    credentialSubject: TradingCard = Field()
    proof: DataIntegrityProof = Field(None)
