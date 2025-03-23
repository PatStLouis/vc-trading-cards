import uvicorn
from asyncio import run as _await
from app.plugins.askar import AskarStorage

if __name__ == "__main__":
    _await(AskarStorage().provision(recreate=True))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # workers=4,
    )
