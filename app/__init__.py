from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.routers import cards

from config import settings

app = FastAPI(title=settings.APP_TITLE, version=settings.APP_VERSION)

api_router = APIRouter()

@api_router.get("/v1", tags=["Context"], include_in_schema=False)
async def app_context():
    """Server status endpoint."""
    return JSONResponse(status_code=200, content={"status": "ok"})

@api_router.get("/server/status", tags=["Server"], include_in_schema=False)
async def server_status():
    """Server status endpoint."""
    return JSONResponse(status_code=200, content={"status": "ok"})

api_router.include_router(cards.router)

app.include_router(api_router)