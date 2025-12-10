from fastapi import APIRouter
from app.api.endpoints import items

api_router = APIRouter()
api_router.include_router(items.router, prefix="/items", tags=["items"])

@api_router.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
