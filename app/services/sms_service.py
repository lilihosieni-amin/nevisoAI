from app.core.config import settings


async def send_otp_sms(phone_number: str, otp_code: str) -> bool:
    """
    Send OTP via SMS (mock implementation)

    In production, integrate with an actual SMS gateway like Twilio, Kavenegar, etc.

    Args:
        phone_number: Recipient phone number
        otp_code: 6-digit OTP code

    Returns:
        True if sent successfully
    """
    # Mock implementation - just print to console
    print(f"[SMS] Sending OTP to {phone_number}: {otp_code}")
    print(f"[SMS] API Key: {settings.SMS_API_KEY}")

    # In production, you would call the SMS gateway API here
    # Example with Kavenegar (Iranian SMS provider):
    # from kavenegar import *
    # try:
    #     api = KavenegarAPI(settings.SMS_API_KEY)
    #     params = {
    #         'receptor': phone_number,
    #         'token': otp_code,
    #         'template': 'otp-template'
    #     }
    #     response = api.verify_lookup(params)
    #     return True
    # except APIException as e:
    #     print(f"SMS API Error: {e}")
    #     return False

    return True
