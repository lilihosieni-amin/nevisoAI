import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings


async def send_otp_email(email: str, otp_code: str) -> bool:
    """
    Send OTP via Email using Gmail SMTP

    Args:
        email: Recipient email address
        otp_code: 6-digit OTP code

    Returns:
        True if sent successfully
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_USERNAME
        msg['To'] = email
        msg['Subject'] = f'کد تأیید نویسو - {otp_code}'

        body = f"""
        <html dir="rtl">
        <body style="font-family: Tahoma, Arial; text-align: center; padding: 20px;">
            <h2>کد تأیید شما</h2>
            <p style="font-size: 32px; font-weight: bold; color: #111; letter-spacing: 8px;">
                {otp_code}
            </p>
            <p>این کد تا ۵ دقیقه معتبر است.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">نویسو - تبدیل هوشمند گفتار به جزوه</p>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html', 'utf-8'))

        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()

        print(f"[EMAIL] OTP sent to {email}")
        return True

    except Exception as e:
        print(f"[EMAIL] Error sending OTP to {email}: {e}")
        return False


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
