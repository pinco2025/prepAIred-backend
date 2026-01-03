from pydantic import BaseModel

class OrderCreateRequest(BaseModel):
    userId: str
    planType: str
    amount: int  # Amount in smallest currency unit (e.g., paise)

class OrderResponse(BaseModel):
    orderId: str
