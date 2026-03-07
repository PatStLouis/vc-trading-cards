"""Public module: catalog (sets, cards), user search, collections. No auth required."""
from .routes import router

__all__ = ["router"]
