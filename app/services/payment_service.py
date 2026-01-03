import json
import logging

import razorpay

from app.core.config import settings
from app.core.supabase import db

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for handling Razorpay payment operations."""

    def __init__(self):
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET

        if self.key_id and self.key_secret:
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
        else:
            self.client = None
            logger.warning("Razorpay keys not set. Payment operations will fail.")

    def create_order(self, user_id: str, plan_type: str, amount: int) -> str:
        """
        Create a Razorpay order with user and plan metadata in notes.
        
        Args:
            user_id: The user's ID
            plan_type: The subscription plan type
            amount: Amount in smallest currency unit (paise for INR)
            
        Returns:
            The Razorpay order ID
        """
        if not self.client:
            raise Exception("Razorpay client not initialized")

        data = {
            "amount": amount,
            "currency": "INR",
            "notes": {
                "userId": user_id,
                "planType": plan_type
            }
        }

        try:
            order = self.client.order.create(data=data)
            return order["id"]
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {e}")
            raise e

    async def process_webhook(self, body: bytes, signature: str):
        """
        Process Razorpay webhook events.
        
        - Verifies webhook signature
        - On 'payment.captured', extracts userId and planType from notes
        - Updates user's tier in Supabase
        """
        if not self.client:
            raise Exception("Razorpay client not initialized")

        # Verify webhook signature
        try:
            self.client.utility.verify_webhook_signature(
                body.decode('utf-8'),
                signature,
                self.webhook_secret
            )
        except Exception as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise ValueError("Invalid signature")

        # Parse event
        event = json.loads(body)

        if event.get("event") == "payment.captured":
            payment_entity = event["payload"]["payment"]["entity"]
            notes = payment_entity.get("notes", {})
            user_id = notes.get("userId")
            plan_type = notes.get("planType")

            if user_id and plan_type:
                await self._update_user_tier(user_id, plan_type)
                logger.info(f"Payment captured: Updated tier for user {user_id} to {plan_type}")
            else:
                logger.warning("Missing userId or planType in payment notes")

    async def _update_user_tier(self, user_id: str, plan_type: str):
        """Update user's tier in Supabase users table."""
        supabase = await db.get_service_client()
        try:
            await supabase.table("users").update({"tier": plan_type}).eq("id", user_id).execute()
            logger.info(f"Updated tier for user {user_id} to {plan_type}")
        except Exception as e:
            logger.error(f"Failed to update user tier: {e}")
            raise e
