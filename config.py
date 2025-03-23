import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):

    APP_TITLE: str = "VC Trading Cards"
    APP_VERSION: str = "v1"

    API_KEY: str = os.getenv("API_KEY", "unsecured")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "unsecured")

    DOMAIN: str = os.getenv("DOMAIN")
    ASKAR_DB: str = os.getenv("ASKAR_DB", "sqlite://app.db")
    
    ISSUER_ID: str = os.getenv("ISSUER_ID", f"did:web:{DOMAIN}")
    ISSUER_NAME: str = os.getenv("ISSUER_NAME", None)
    ISSUER_IMAGE: str = os.getenv("ISSUER_IMAGE", None)
    
    CRED_NAME: str = os.getenv("CRED_NAME", None)
    CRED_DESC: str = os.getenv("CRED_DESC", None)


settings = Settings()
