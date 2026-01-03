from pydantic import BaseModel


class OrderCreateRequest(BaseModel):
    """Request body for creating a Razorpay order."""
    userId: str
    planType: str
    amount: int  # Amount in smallest currency unit (e.g., paise)


class OrderResponse(BaseModel):
    """Response body containing the created order ID."""
    orderId: str
