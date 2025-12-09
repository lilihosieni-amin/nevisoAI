from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.user import OTPRequest, OTPVerify, TokenResponse, UserResponse, EmailOTPRequest, EmailOTPVerify
from app.crud import user as user_crud
from app.core.security import generate_otp, create_access_token, create_refresh_token
from app.services.sms_service import send_otp_sms, send_otp_email
from datetime import datetime, timedelta

router = APIRouter()


@router.post("/request-otp", status_code=status.HTTP_200_OK)
async def request_otp(
    request: OTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request OTP for phone number authentication
    Creates user if doesn't exist
    """
    try:
        user = await user_crud.get_user_by_phone(db, request.phone_number)
        is_new_user = False
        if not user:
            from app.schemas.user import UserCreate
            print(f"[AUTH] Creating new user with phone: {request.phone_number}")
            user = await user_crud.create_user(db, UserCreate(phone_number=request.phone_number))
            is_new_user = True
            print(f"[AUTH] User created with ID: {user.id}, now granting welcome credit")
            # Grant welcome credit to new user
            result = await user_crud.grant_welcome_credit(db, user.id)
            print(f"[AUTH] grant_welcome_credit returned: {result}")

        otp_code = generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        await user_crud.create_otp(db, user.id, otp_code, expires_at)
        await send_otp_sms(request.phone_number, otp_code)

        return { "success": True, "message": "OTP sent successfully", "expires_in": 300 }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send OTP: {str(e)}"
        )


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
    request: OTPVerify,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify OTP, set HTTPOnly cookie, and return tokens
    """
    user = await user_crud.get_user_by_phone(db, request.phone_number)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    otp = await user_crud.get_valid_otp(db, user.id, request.otp_code)
    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    await user_crud.mark_otp_used(db, otp.id)

    # --- ✅ **تغییر اصلی اینجاست** ---
    # شناسه کاربری را به رشته تبدیل می‌کنیم
    user_id_str = str(user.id)
    access_token = create_access_token(data={"sub": user_id_str})
    refresh_token = create_refresh_token(data={"sub": user_id_str})

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=1800
    )

    return TokenResponse(
        access_token=access_token, # ارسال در بدنه پاسخ هم مشکلی ایجاد نمی‌کند
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user)
    )


@router.post("/request-email-otp", status_code=status.HTTP_200_OK)
async def request_email_otp(
    request: EmailOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request OTP for email authentication
    Creates user if doesn't exist
    """
    try:
        user = await user_crud.get_user_by_email(db, request.email)
        is_new_user = False
        if not user:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[AUTH] Creating new user with email: {request.email}")
            user = await user_crud.create_user_by_email(db, request.email)
            is_new_user = True
            logger.info(f"[AUTH] User created with ID: {user.id}, now granting welcome credit")
            # Grant welcome credit to new user
            result = await user_crud.grant_welcome_credit(db, user.id)
            logger.info(f"[AUTH] grant_welcome_credit returned: {result}")

        otp_code = generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        await user_crud.create_otp(db, user.id, otp_code, expires_at)
        await send_otp_email(request.email, otp_code)

        return {"success": True, "message": "OTP sent to email successfully", "expires_in": 300}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send OTP: {str(e)}"
        )


@router.post("/verify-email-otp", response_model=TokenResponse)
async def verify_email_otp(
    request: EmailOTPVerify,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify email OTP, set HTTPOnly cookie, and return tokens
    """
    user = await user_crud.get_user_by_email(db, request.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    otp = await user_crud.get_valid_otp(db, user.id, request.otp_code)
    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    await user_crud.mark_otp_used(db, otp.id)

    user_id_str = str(user.id)
    access_token = create_access_token(data={"sub": user_id_str})
    refresh_token = create_refresh_token(data={"sub": user_id_str})

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=1800
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user)
    )