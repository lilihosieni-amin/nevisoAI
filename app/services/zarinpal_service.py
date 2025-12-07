"""
ZarinPal Payment Gateway Service
Handles payment creation, verification, and callbacks
"""
import httpx
import logging
from typing import Dict, Optional
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)


class ZarinpalError(Exception):
    """Base exception for ZarinPal errors"""
    pass


class ZarinpalGateway:
    """
    ZarinPal Payment Gateway Integration

    Docs: https://docs.zarinpal.com/paymentGateway/
    """

    # Production URLs
    BASE_URL = "https://api.zarinpal.com/pg/v4/payment"
    PAYMENT_URL = "https://www.zarinpal.com/pg/StartPay"

    # Sandbox URLs
    SANDBOX_BASE_URL = "https://sandbox.zarinpal.com/pg/v4/payment"
    SANDBOX_PAYMENT_URL = "https://sandbox.zarinpal.com/pg/StartPay"

    def __init__(self):
        self.merchant_id = settings.ZARINPAL_MERCHANT_ID
        self.is_sandbox = settings.ZARINPAL_SANDBOX

        # Select appropriate URLs based on environment
        if self.is_sandbox:
            self.base_url = self.SANDBOX_BASE_URL
            self.payment_url = self.SANDBOX_PAYMENT_URL
            logger.info("ZarinPal initialized in SANDBOX mode")
        else:
            self.base_url = self.BASE_URL
            self.payment_url = self.PAYMENT_URL
            logger.info("ZarinPal initialized in PRODUCTION mode")

    async def create_payment(
        self,
        amount: int,  # Amount in Toman
        description: str,
        callback_url: str,
        mobile: Optional[str] = None,
        email: Optional[str] = None,
        order_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Create a new payment request

        Args:
            amount: Payment amount in Toman
            description: Payment description (shown to user)
            callback_url: URL to redirect after payment
            mobile: User's mobile number (optional)
            email: User's email (optional)
            order_id: Your internal order ID (optional)

        Returns:
            Dict with 'authority' and 'payment_url' keys

        Raises:
            ZarinpalError: If payment creation fails
        """
        try:
            logger.info(f"Creating ZarinPal payment: amount={amount} Toman, desc='{description}'")

            # Prepare request data
            request_data = {
                "merchant_id": self.merchant_id,
                "amount": amount * 10,  # Convert Toman to Rial
                "description": description,
                "callback_url": callback_url
            }

            # Add optional metadata
            metadata = {}
            if mobile:
                metadata["mobile"] = mobile
            if email:
                metadata["email"] = email
            if order_id:
                metadata["order_id"] = order_id

            if metadata:
                request_data["metadata"] = metadata

            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/request.json",
                    json=request_data
                )

                logger.info(f"ZarinPal response status: {response.status_code}")

                # Parse response
                response_data = response.json()

                # Check for errors
                if response.status_code != 200:
                    error_msg = response_data.get("errors", {})
                    logger.error(f"ZarinPal payment creation failed: {error_msg}")
                    raise ZarinpalError(f"Payment creation failed: {error_msg}")

                # Get data from response
                data = response_data.get("data", {})
                code = data.get("code")
                authority = data.get("authority")

                # Check response code
                if code != 100:
                    error_message = self._get_error_message(code)
                    logger.error(f"ZarinPal returned error code {code}: {error_message}")
                    raise ZarinpalError(f"Payment error: {error_message}")

                if not authority:
                    logger.error("ZarinPal response missing authority code")
                    raise ZarinpalError("Missing authority code in response")

                # Generate payment URL
                payment_url = f"{self.payment_url}/{authority}"

                logger.info(f"Payment created successfully. Authority: {authority}")

                return {
                    "authority": authority,
                    "payment_url": payment_url
                }

        except httpx.TimeoutException:
            logger.error("ZarinPal API request timed out")
            raise ZarinpalError("Payment gateway timeout. Please try again.")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
            raise ZarinpalError(f"Connection error: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error in create_payment: {str(e)}", exc_info=True)
            raise ZarinpalError(f"Payment creation error: {str(e)}")

    async def verify_payment(
        self,
        authority: str,
        amount: int  # Amount in Toman
    ) -> Dict[str, any]:
        """
        Verify a payment after user returns from payment gateway

        Args:
            authority: Authority code from payment creation
            amount: Original payment amount in Toman

        Returns:
            Dict with verification details including:
            - ref_id: Unique reference ID from ZarinPal
            - card_pan: Masked card number (last 4 digits)
            - card_hash: Hashed card number
            - fee_type: Fee type
            - fee: Transaction fee

        Raises:
            ZarinpalError: If verification fails
        """
        try:
            logger.info(f"Verifying ZarinPal payment: authority={authority}, amount={amount}")

            # Prepare request data
            request_data = {
                "merchant_id": self.merchant_id,
                "amount": amount * 10,  # Convert Toman to Rial
                "authority": authority
            }

            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/verify.json",
                    json=request_data
                )

                logger.info(f"ZarinPal verify response status: {response.status_code}")

                # Parse response
                response_data = response.json()

                # Check for errors
                if response.status_code != 200:
                    error_msg = response_data.get("errors", {})
                    logger.error(f"ZarinPal verification failed: {error_msg}")
                    raise ZarinpalError(f"Verification failed: {error_msg}")

                # Get data from response
                data = response_data.get("data", {})
                code = data.get("code")

                # Check response code
                if code == 100:
                    # Payment successful
                    ref_id = data.get("ref_id")
                    card_pan = data.get("card_pan")
                    card_hash = data.get("card_hash")
                    fee_type = data.get("fee_type")
                    fee = data.get("fee")

                    logger.info(f"Payment verified successfully. Ref ID: {ref_id}")

                    return {
                        "success": True,
                        "ref_id": ref_id,
                        "card_pan": card_pan,
                        "card_hash": card_hash,
                        "fee_type": fee_type,
                        "fee": fee,
                        "verified_at": datetime.utcnow().isoformat()
                    }

                elif code == 101:
                    # Payment already verified
                    logger.warning(f"Payment already verified: {authority}")
                    return {
                        "success": True,
                        "already_verified": True,
                        "ref_id": data.get("ref_id"),
                        "message": "Payment already verified"
                    }

                else:
                    # Payment failed
                    error_message = self._get_error_message(code)
                    logger.error(f"Payment verification failed with code {code}: {error_message}")
                    raise ZarinpalError(f"Payment failed: {error_message}")

        except httpx.TimeoutException:
            logger.error("ZarinPal verify API request timed out")
            raise ZarinpalError("Verification timeout. Please contact support.")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during verification: {str(e)}")
            raise ZarinpalError(f"Connection error: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error in verify_payment: {str(e)}", exc_info=True)
            raise ZarinpalError(f"Verification error: {str(e)}")

    async def unverified_transactions(self) -> Dict[str, any]:
        """
        Get list of unverified transactions (last 100)
        Useful for reconciliation

        Returns:
            Dict with list of unverified authorities
        """
        try:
            logger.info("Fetching unverified transactions from ZarinPal")

            request_data = {
                "merchant_id": self.merchant_id
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/unVerified.json",
                    json=request_data
                )

                response_data = response.json()

                if response.status_code == 200:
                    data = response_data.get("data", {})
                    authorities = data.get("authorities", [])
                    logger.info(f"Found {len(authorities)} unverified transactions")
                    return {
                        "success": True,
                        "authorities": authorities
                    }
                else:
                    logger.error(f"Failed to fetch unverified transactions: {response_data}")
                    return {
                        "success": False,
                        "error": response_data
                    }

        except Exception as e:
            logger.error(f"Error fetching unverified transactions: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def _get_error_message(code: int) -> str:
        """Get human-readable error message for ZarinPal error codes"""
        error_messages = {
            -1: "اطلاعات ارسال شده ناقص است",
            -2: "IP یا مرچنت کد پذیرنده صحیح نیست",
            -3: "با توجه به محدودیت‌های شاپرک امکان پرداخت با رقم درخواست شده میسر نمی‌باشد",
            -4: "سطح تایید پذیرنده پایین‌تر از سطح نقره‌ای است",
            -11: "درخواست مورد نظر یافت نشد",
            -12: "امکان ویرایش درخواست میسر نمی‌باشد",
            -21: "هیچ نوع عملیات مالی برای این تراکنش یافت نشد",
            -22: "تراکنش ناموفق می‌باشد",
            -33: "رقم تراکنش با رقم پرداخت شده مطابقت ندارد",
            -34: "سقف تقسیم تراکنش از لحاظ تعداد یا رقم عبور کرده است",
            -40: "اجازه دسترسی به متد مربوطه وجود ندارد",
            -41: "اطلاعات ارسال شده مربوط به AdditionalData غیر معتبر است",
            -42: "مدت زمان معتبر طول عمر شناسه پرداخت باید بین 30 دقیقه تا 45 روز باشد",
            -54: "درخواست مورد نظر آرشیو شده است",
            100: "عملیات موفق",
            101: "عملیات پرداخت موفق بوده و قبلا تایید شده است"
        }
        return error_messages.get(code, f"خطای ناشناخته (کد {code})")


# Singleton instance
zarinpal_gateway = ZarinpalGateway()
