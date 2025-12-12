import logging
from typing import Optional
from supabase import create_async_client, AsyncClient
from app.core.config import settings

logger = logging.getLogger(__name__)

class SupabaseManager:
    client: Optional[AsyncClient] = None
    service_client: Optional[AsyncClient] = None

    @classmethod
    async def get_client(cls) -> AsyncClient:
        if cls.client is None:
            url: str = settings.SUPABASE_URL
            key: str = settings.SUPABASE_KEY
            if not url or not key:
                raise ValueError("Supabase URL and Key must be provided in the environment variables.")
            cls.client = await create_async_client(url, key)
        return cls.client

    @classmethod
    async def get_service_client(cls) -> AsyncClient:
        """
        Returns a Supabase client initialized with the Service Role Key if available.
        Falls back to the standard client (SUPABASE_KEY) if not.
        """
        if cls.service_client is None:
            url: str = settings.SUPABASE_URL
            key: Optional[str] = settings.SUPABASE_SERVICE_ROLE_KEY

            if key:
                logger.info("Initializing Supabase client with Service Role Key.")
                cls.service_client = await create_async_client(url, key)
            else:
                logger.warning("SUPABASE_SERVICE_ROLE_KEY not found. Falling back to standard SUPABASE_KEY. RLS might block access.")
                return await cls.get_client()

        return cls.service_client

# Global instance to access the client manager
db = SupabaseManager()
