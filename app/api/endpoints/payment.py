from fastapi import APIRouter, HTTPException, Request, Header
from app.schemas.payment import OrderCreateRequest, OrderResponse
from app.services.payment_service import PaymentService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/create-order", response_model=OrderResponse)
async def create_order(request: OrderCreateRequest):
    """
    Create a Razorpay order for payment.
    
    Accepts: userId, planType, amount
    Returns: orderId
    """
    service = PaymentService()
    try:
        order_id = service.create_order(request.userId, request.planType, request.amount)
        return OrderResponse(orderId=order_id)
    except Exception as e:
        logger.error(f"Failed to create order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/razorpay-webhook")
async def razorpay_webhook(request: Request, x_razorpay_signature: str = Header(None)):
    """
    Handle Razorpay webhook events.
    
    - Verifies webhook signature using RAZORPAY_WEBHOOK_SECRET
    - On 'payment.captured' event, extracts userId and planType from payment.notes
    - Updates Supabase users table: set tier = planType
    - Returns 200 OK
    """
    if x_razorpay_signature is None:
        raise HTTPException(status_code=400, detail="Missing signature header")

    service = PaymentService()
    body = await request.body()

    try:
        await service.process_webhook(body, x_razorpay_signature)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
