import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api import api_router
from app.api.endpoints import payment
from app.core.supabase import db

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Supabase Client
    try:
        await db.get_client()
        logger.info("Supabase client initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
    yield
    # Clean up resources if needed

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], #str(origin) for origin in settings.BACKEND_CORS_ORIGINS
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )

# Include Router
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(payment.router, prefix="/api", tags=["payment"])

@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI Supabase Boilerplate"}

@app.post("/")
async def handle_payment_return(request: Request):
    # This handler catches the POST request from Razorpay redirect (if configured as callback_url)
    # It attempts to verify the payment and return a response.
    # In a real app, this should probably redirect to a frontend success/failure page.
    from app.services.payment_service import PaymentService

    try:
        form_data = await request.form()
        params = {
            "razorpay_order_id": form_data.get("razorpay_order_id"),
            "razorpay_payment_id": form_data.get("razorpay_payment_id"),
            "razorpay_signature": form_data.get("razorpay_signature")
        }

        if not all(params.values()):
             return JSONResponse(status_code=400, content={"message": "Missing payment parameters"})

        service = PaymentService()
        result = await service.process_payment_completion(params)

        return JSONResponse(content={"message": "Payment processed successfully", "status": "verified", "details": result})

    except Exception as e:
        logger.error(f"Error handling payment return at root: {e}")
        return JSONResponse(status_code=400, content={"message": "Payment verification failed", "detail": str(e)})
