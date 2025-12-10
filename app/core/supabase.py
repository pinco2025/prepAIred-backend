from typing import Optional
from supabase import create_async_client, AsyncClient
from app.core.config import settings

class SupabaseManager:
    client: Optional[AsyncClient] = None

    @classmethod
    async def get_client(cls) -> AsyncClient:
        if cls.client is None:
            url: str = settings.SUPABASE_URL
            key: str = settings.SUPABASE_KEY
            if not url or not key:
                raise ValueError("Supabase URL and Key must be provided in the environment variables.")
            cls.client = await create_async_client(url, key)
        return cls.client

# Global instance to access the client manager
db = SupabaseManager()
