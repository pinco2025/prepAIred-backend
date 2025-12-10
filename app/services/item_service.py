from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
from app.core.supabase import db
from app.schemas.item import ItemCreate, ItemUpdate, Item

class ItemService:
    def __init__(self):
        self.table = "items"

    async def get_items(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        client = await db.get_client()
        # postgrest-py with AsyncClient:
        # .select("*") returns a builder, .range(...) returns builder, .execute() is awaitable?
        # Let's verify standard usage.
        # Usually: await client.table("items").select("*").range(skip, skip + limit - 1).execute()

        result = await client.table(self.table).select("*").range(skip, skip + limit - 1).execute()
        return result.data

    async def create_item(self, item_in: ItemCreate, owner_id: uuid.UUID) -> Dict[str, Any]:
        client = await db.get_client()
        item_data = item_in.model_dump()
        item_data["owner_id"] = str(owner_id) # Ensure UUID is stringified for JSON serialization

        # Supabase returns the inserted data
        result = await client.table(self.table).insert(item_data).execute()
        if result.data:
            return result.data[0]
        return None

    async def get_item(self, item_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        client = await db.get_client()
        result = await client.table(self.table).select("*").eq("id", str(item_id)).execute()
        if result.data:
            return result.data[0]
        return None

    async def update_item(self, item_id: uuid.UUID, item_in: ItemUpdate) -> Optional[Dict[str, Any]]:
        client = await db.get_client()
        update_data = item_in.model_dump(exclude_unset=True)
        if not update_data:
            return await self.get_item(item_id)

        result = await client.table(self.table).update(update_data).eq("id", str(item_id)).execute()
        if result.data:
            return result.data[0]
        return None

    async def delete_item(self, item_id: uuid.UUID) -> bool:
        client = await db.get_client()
        # Count is not returned by default in delete unless generic specified?
        # But data is returned.
        result = await client.table(self.table).delete().eq("id", str(item_id)).execute()
        return bool(result.data)
