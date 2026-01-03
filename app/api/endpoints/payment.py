from fastapi import APIRouter, HTTPException, Request, Header
from app.schemas.payment import OrderCreateRequest, OrderResponse, PaymentVerificationRequest
from app.services.payment_service import PaymentService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/create-order", response_model=OrderResponse)
async def create_order(request: OrderCreateRequest):
    service = PaymentService()
    try:
        order_id = service.create_order(request.userId, request.planType, request.amount)
        return OrderResponse(orderId=order_id)
    except Exception as e:
        logger.error(f"Failed to create order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-payment")
async def verify_payment(request: PaymentVerificationRequest):
    service = PaymentService()
    try:
        params = {
            "razorpay_order_id": request.razorpay_order_id,
            "razorpay_payment_id": request.razorpay_payment_id,
            "razorpay_signature": request.razorpay_signature
        }
        result = await service.process_payment_completion(params)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Payment verification failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/razorpay-webhook")
async def razorpay_webhook(request: Request, x_razorpay_signature: str = Header(None)):
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
