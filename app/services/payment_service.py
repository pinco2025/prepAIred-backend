import razorpay
import logging
from app.core.config import settings
from app.core.supabase import db

logger = logging.getLogger(__name__)

class PaymentService:
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

    async def process_payment_completion(self, params: dict):
        """
        Verifies payment signature, fetches order details, and updates user subscription.
        Returns a dict with status.
        """
        if not self.client:
            raise Exception("Razorpay client not initialized")

        # 1. Verify Signature
        try:
            self.client.utility.verify_payment_signature(params)
        except Exception as e:
            logger.error(f"Payment signature verification failed: {e}")
            raise ValueError("Invalid payment signature")

        # 2. Fetch Order to get metadata
        order_id = params.get("razorpay_order_id")
        try:
            order = self.client.order.fetch(order_id)
        except Exception as e:
            logger.error(f"Error fetching order {order_id}: {e}")
            raise ValueError(f"Could not fetch order: {e}")

        # 3. Update Subscription
        if "notes" in order and "userId" in order["notes"] and "planType" in order["notes"]:
            user_id = order["notes"]["userId"]
            plan_type = order["notes"]["planType"]
            await self._update_user_subscription(user_id, plan_type)
            return {"status": "verified", "user_id": user_id, "plan_type": plan_type}
        else:
            logger.warning(f"Order {order_id} missing notes for subscription update")
            return {"status": "verified", "message": "Subscription update skipped due to missing metadata"}

    async def process_webhook(self, body: bytes, signature: str):
        if not self.client:
            raise Exception("Razorpay client not initialized")

        # Verify signature
        try:
            self.client.utility.verify_webhook_signature(
                body.decode('utf-8'),
                signature,
                self.webhook_secret
            )
        except Exception as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise ValueError("Invalid signature")

        # Parse event (using standard json since body is bytes)
        import json
        event = json.loads(body)

        if event.get("event") == "payment.captured":
            payment_entity = event["payload"]["payment"]["entity"]
            notes = payment_entity.get("notes", {})
            user_id = notes.get("userId")
            plan_type = notes.get("planType")

            if user_id and plan_type:
                await self._update_user_subscription(user_id, plan_type)
            else:
                logger.warning("Missing userId or planType in payment notes")

    async def _update_user_subscription(self, user_id: str, plan_type: str):
        supabase = await db.get_service_client()
        try:
            # We assume there is a 'users' table (usually 'auth.users' is protected,
            # but often apps have a public 'users' or 'profiles' table.
            # The prompt says 'Supabase users table'.
            # If it refers to `auth.users`, we can't update it easily via client unless using admin api which supabase-py might support if service role key is used.
            # However, typically application data is in `public.users` or similar.
            # I will attempt to update `users` table in public schema.

            response = await supabase.table("users").update({"subscription_tier": plan_type}).eq("id", user_id).execute()
            logger.info(f"Updated subscription for user {user_id} to {plan_type}")
        except Exception as e:
            logger.error(f"Failed to update user subscription: {e}")
            raise e
