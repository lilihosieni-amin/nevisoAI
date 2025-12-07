from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.subscription import PaymentCreate, PaymentResponse
from app.crud import plan as plan_crud
from app.crud import subscription as subscription_crud
from app.core.dependencies import get_current_user_from_cookie
from app.db.models import User, SubscriptionStatus, PaymentStatus
from datetime import datetime, timedelta
import uuid

router = APIRouter()


@router.post("/create-checkout", response_model=PaymentResponse)
async def create_checkout(
    payment_request: PaymentCreate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a payment checkout session (mock payment gateway)
    """
    # Get plan
    plan = await plan_crud.get_plan_by_id(db, payment_request.plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )

    # Create subscription with pending status
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=plan.duration_days)

    subscription = await subscription_crud.create_subscription(
        db=db,
        user_id=current_user.id,
        plan_id=plan.id,
        start_date=start_date,
        end_date=end_date,
        status=SubscriptionStatus.active  # Set to pending initially, but we'll use active for simplicity
    )

    # Create payment record
    transaction_ref_id = str(uuid.uuid4())
    payment = await subscription_crud.create_payment(
        db=db,
        user_id=current_user.id,
        subscription_id=subscription.id,
        amount_toman=int(plan.price_toman),
        transaction_ref_id=transaction_ref_id,
        payment_gateway="mock",
        status=PaymentStatus.pending
    )

    # Generate mock payment URL
    payment_url = f"http://localhost:8000/api/v1/payments/callback?payment_id={payment.id}&status=success"

    return PaymentResponse(payment_url=payment_url)


@router.get("/callback")
async def payment_callback(
    payment_id: int,
    status: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Mock payment gateway callback
    In production, this would verify the payment with the gateway
    """
    # Get payment
    payment = await subscription_crud.get_payment_by_id(db, payment_id)
    if not payment:
        return RedirectResponse(url="/profile?payment=failed&error=payment_not_found")

    if status == "success":
        # Update payment status
        await subscription_crud.update_payment_status(db, payment_id, PaymentStatus.completed)

        # Update subscription status
        await subscription_crud.update_subscription_status(
            db,
            payment.subscription_id,
            SubscriptionStatus.active
        )

        return RedirectResponse(url="/profile?payment=success")
    else:
        # Update payment status to failed
        await subscription_crud.update_payment_status(db, payment_id, PaymentStatus.failed)

        # Update subscription status to cancelled
        await subscription_crud.update_subscription_status(
            db,
            payment.subscription_id,
            SubscriptionStatus.cancelled
        )

        return RedirectResponse(url="/profile?payment=failed")
