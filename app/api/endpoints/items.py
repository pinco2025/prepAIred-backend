from typing import Any, List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.item import Item, ItemCreate, ItemUpdate
from app.schemas.common import APIResponse
from app.services.item_service import ItemService
from app.api.deps import get_current_user, TokenData

router = APIRouter()
item_service = ItemService()

@router.get("/", response_model=APIResponse[List[Item]])
async def read_items(
    skip: int = 0,
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user)
) -> Any:
    """
    Retrieve items.
    """
    try:
        items = await item_service.get_items(skip=skip, limit=limit)
        return APIResponse(data=items)
    except Exception as e:
        # In a real app, you'd want to handle specific exceptions
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=APIResponse[Item])
async def create_item(
    *,
    item_in: ItemCreate,
    current_user: TokenData = Depends(get_current_user)
) -> Any:
    """
    Create new item.
    """
    try:
        # We use the current_user.id as the owner_id
        item = await item_service.create_item(item_in=item_in, owner_id=uuid.UUID(current_user.id))
        return APIResponse(data=item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{item_id}", response_model=APIResponse[Item])
async def read_item(
    *,
    item_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user)
) -> Any:
    """
    Get item by ID.
    """
    item = await item_service.get_item(item_id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return APIResponse(data=item)

@router.put("/{item_id}", response_model=APIResponse[Item])
async def update_item(
    *,
    item_id: uuid.UUID,
    item_in: ItemUpdate,
    current_user: TokenData = Depends(get_current_user)
) -> Any:
    """
    Update an item.
    """
    item = await item_service.get_item(item_id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check permissions if needed (e.g. only owner can update)
    if item["owner_id"] != current_user.id:
         # Note: owner_id in DB is UUID string, current_user.id is string from token.
         # They should match.
         raise HTTPException(status_code=403, detail="Not authorized to update this item")

    try:
        updated_item = await item_service.update_item(item_id=item_id, item_in=item_in)
        return APIResponse(data=updated_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{item_id}", response_model=APIResponse[bool])
async def delete_item(
    *,
    item_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user)
) -> Any:
    """
    Delete an item.
    """
    item = await item_service.get_item(item_id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        result = await item_service.delete_item(item_id=item_id)
        return APIResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
