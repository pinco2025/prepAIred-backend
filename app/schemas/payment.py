from pydantic import BaseModel

class OrderCreateRequest(BaseModel):
    userId: str
    planType: str
    amount: int  # Amount in smallest currency unit (e.g., paise)

class OrderResponse(BaseModel):
    orderId: str

class PaymentVerificationRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
