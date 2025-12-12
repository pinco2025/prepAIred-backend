from fastapi import APIRouter
from app.api.endpoints import scores

api_router = APIRouter()
api_router.include_router(scores.router, prefix="/scores", tags=["scores"])

@api_router.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
