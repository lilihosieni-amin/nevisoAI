"""
Payment API Endpoints with ZarinPal Integration
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from app.db.session import get_db
from app.core.dependencies import get_current_user_from_cookie
from app.db.models import User, SubscriptionStatus, PaymentStatus, Payment
from app.crud import plan as plan_crud
from app.crud import subscription as subscription_crud
from app.services.zarinpal_service import zarinpal_gateway, ZarinpalError
from app.services.credit_service import credit_manager
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class PaymentCreateRequest(BaseModel):
    plan_id: int


class PaymentCreateResponse(BaseModel):
    payment_id: int
    payment_url: str
    authority: str


@router.post("/create", response_model=PaymentCreateResponse)
async def create_payment(
    payment_request: PaymentCreateRequest,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    ایجاد پرداخت جدید برای خرید پلن

    Args:
        payment_request: شامل plan_id

    Returns:
        URL پرداخت ZarinPal
    """
    try:
        # Get plan
        plan = await plan_crud.get_plan_by_id(db, payment_request.plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="پلن یافت نشد"
            )

        if not plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="این پلن غیرفعال است"
            )

        # Create subscription with pending status first
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=plan.duration_days)

        subscription = await subscription_crud.create_subscription(
            db=db,
            user_id=current_user.id,
            plan_id=plan.id,
            start_date=start_date,
            end_date=end_date,
            status=SubscriptionStatus.cancelled  # Will activate after payment
        )

        # Create payment record with pending status
        from sqlalchemy import insert, select
        from app.db.models import Payment

        # Generate temporary transaction_ref_id (will be updated with authority)
        temp_ref_id = f"PENDING_{subscription.id}_{int(datetime.utcnow().timestamp())}"

        payment_stmt = insert(Payment).values(
            user_id=current_user.id,
            subscription_id=subscription.id,
            amount_toman=int(plan.price_toman),
            payment_gateway="zarinpal",
            transaction_ref_id=temp_ref_id,
            status=PaymentStatus.pending
        )
        result = await db.execute(payment_stmt)
        await db.commit()
        payment_id = result.inserted_primary_key[0]

        # Get payment object
        payment_result = await db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = payment_result.scalar_one()

        # Create ZarinPal payment
        callback_url = f"{settings.ZARINPAL_CALLBACK_URL}?payment_id={payment_id}"

        try:
            zarinpal_response = await zarinpal_gateway.create_payment(
                amount=int(plan.price_toman),
                description=f"خرید پلن {plan.name} - نویسو",
                callback_url=callback_url,
                mobile=current_user.phone_number,
                email=current_user.email,
                order_id=str(payment_id)
            )

            # Update payment with authority
            payment.transaction_ref_id = zarinpal_response['authority']
            await db.commit()

            logger.info(
                f"Payment created: payment_id={payment_id}, "
                f"authority={zarinpal_response['authority']}, "
                f"user={current_user.id}"
            )

            return PaymentCreateResponse(
                payment_id=payment_id,
                payment_url=zarinpal_response['payment_url'],
                authority=zarinpal_response['authority']
            )

        except ZarinpalError as e:
            # Mark payment as failed
            payment.status = PaymentStatus.failed
            await db.commit()

            logger.error(f"ZarinPal error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"خطا در اتصال به درگاه پرداخت: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating payment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در ایجاد پرداخت: {str(e)}"
        )


@router.get("/callback")
async def payment_callback(
    request: Request,
    payment_id: int,
    Authority: str,
    Status: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Callback از درگاه ZarinPal پس از پرداخت

    Query params:
        - payment_id: شناسه پرداخت داخلی
        - Authority: کد authority از ZarinPal
        - Status: وضعیت پرداخت (OK یا NOK)
    """
    try:
        logger.info(
            f"Payment callback: payment_id={payment_id}, "
            f"Authority={Authority}, Status={Status}"
        )

        # Get payment from database
        from sqlalchemy import select
        payment_result = await db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = payment_result.scalar_one_or_none()

        if not payment:
            logger.error(f"Payment not found: {payment_id}")
            return RedirectResponse(
                url="/profile?payment=failed&error=payment_not_found"
            )

        # Check if payment was successful (Status == 'OK')
        if Status != 'OK':
            logger.warning(f"Payment cancelled by user: {payment_id}")

            # Update payment status
            payment.status = PaymentStatus.failed
            await db.commit()

            return RedirectResponse(
                url="/profile?payment=cancelled"
            )

        # Verify payment with ZarinPal
        try:
            verification = await zarinpal_gateway.verify_payment(
                authority=Authority,
                amount=int(payment.amount_toman)
            )

            if verification.get('success'):
                # Payment successful
                ref_id = verification.get('ref_id')

                # Update payment status
                payment.status = PaymentStatus.completed
                payment.paid_at = datetime.utcnow()
                # Store ref_id in transaction_ref_id with authority
                payment.transaction_ref_id = f"{Authority}|{ref_id}"

                # Activate subscription
                await subscription_crud.update_subscription_status(
                    db,
                    payment.subscription_id,
                    SubscriptionStatus.active
                )

                # Log credit purchase transaction
                from sqlalchemy import select as sql_select
                from app.db.models import UserSubscription
                sub_result = await db.execute(
                    sql_select(UserSubscription)
                    .join(UserSubscription.plan)
                    .where(UserSubscription.id == payment.subscription_id)
                )
                subscription = sub_result.scalar_one()

                await credit_manager.log_purchase_transaction(
                    db,
                    payment.user_id,
                    subscription.id,
                    subscription.plan.max_minutes,
                    f"خرید پلن {subscription.plan.name}"
                )

                await db.commit()

                logger.info(
                    f"Payment verified successfully: payment_id={payment_id}, "
                    f"ref_id={ref_id}"
                )

                return RedirectResponse(
                    url=f"/profile?payment=success&ref_id={ref_id}"
                )

            else:
                # Verification failed
                logger.error(f"Payment verification failed: {payment_id}")

                payment.status = PaymentStatus.failed
                await db.commit()

                return RedirectResponse(
                    url="/profile?payment=failed&error=verification_failed"
                )

        except ZarinpalError as e:
            logger.error(f"ZarinPal verification error: {str(e)}")

            payment.status = PaymentStatus.failed
            await db.commit()

            return RedirectResponse(
                url=f"/profile?payment=failed&error={str(e)}"
            )

    except Exception as e:
        logger.error(f"Error in payment callback: {str(e)}", exc_info=True)
        return RedirectResponse(
            url="/profile?payment=failed&error=system_error"
        )


@router.get("/verify/{payment_id}")
async def check_payment_status(
    payment_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    بررسی وضعیت پرداخت

    Args:
        payment_id: شناسه پرداخت

    Returns:
        وضعیت پرداخت
    """
    try:
        from sqlalchemy import select

        # Get payment
        result = await db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="پرداخت یافت نشد"
            )

        # Check ownership
        if payment.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="دسترسی غیرمجاز"
            )

        return {
            'payment_id': payment.id,
            'amount': float(payment.amount_toman),
            'status': payment.status.value,
            'gateway': payment.payment_gateway,
            'transaction_ref_id': payment.transaction_ref_id,
            'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
            'created_at': payment.created_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در بررسی وضعیت: {str(e)}"
        )


@router.get("/history")
async def get_payment_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت تاریخچه پرداخت‌های کاربر

    Args:
        limit: تعداد رکورد
        offset: شروع از رکورد

    Returns:
        لیست پرداخت‌ها
    """
    try:
        from sqlalchemy import select, desc

        result = await db.execute(
            select(Payment)
            .where(Payment.user_id == current_user.id)
            .order_by(desc(Payment.created_at))
            .limit(limit)
            .offset(offset)
        )
        payments = result.scalars().all()

        return [
            {
                'payment_id': p.id,
                'amount': float(p.amount_toman),
                'status': p.status.value,
                'gateway': p.payment_gateway,
                'paid_at': p.paid_at.isoformat() if p.paid_at else None,
                'created_at': p.created_at.isoformat()
            }
            for p in payments
        ]

    except Exception as e:
        logger.error(f"Error getting payment history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت تاریخچه: {str(e)}"
        )
