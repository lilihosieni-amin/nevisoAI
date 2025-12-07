from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import UserSubscription, Payment, SubscriptionStatus, PaymentStatus
from typing import Optional
from datetime import datetime


async def create_subscription(
    db: AsyncSession,
    user_id: int,
    plan_id: int,
    start_date: datetime,
    end_date: datetime,
    status: SubscriptionStatus = SubscriptionStatus.active
) -> UserSubscription:
    """Create a new subscription"""
    subscription = UserSubscription(
        user_id=user_id,
        plan_id=plan_id,
        start_date=start_date,
        end_date=end_date,
        status=status
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def get_active_subscription(db: AsyncSession, user_id: int) -> Optional[UserSubscription]:
    """Get user's active subscription"""
    result = await db.execute(
        select(UserSubscription)
        .where(
            UserSubscription.user_id == user_id,
            UserSubscription.status == SubscriptionStatus.active,
            UserSubscription.end_date > datetime.utcnow()
        )
        .order_by(UserSubscription.end_date.desc())
    )
    return result.scalar_one_or_none()


async def update_subscription_status(
    db: AsyncSession,
    subscription_id: int,
    status: SubscriptionStatus
) -> Optional[UserSubscription]:
    """Update subscription status"""
    result = await db.execute(
        select(UserSubscription).where(UserSubscription.id == subscription_id)
    )
    subscription = result.scalar_one_or_none()
    if subscription:
        subscription.status = status
        await db.commit()
        await db.refresh(subscription)
    return subscription


async def create_payment(
    db: AsyncSession,
    user_id: int,
    subscription_id: int,
    amount_toman: int,
    transaction_ref_id: str,
    payment_gateway: str = "mock",
    status: PaymentStatus = PaymentStatus.pending
) -> Payment:
    """Create a payment record"""
    payment = Payment(
        user_id=user_id,
        subscription_id=subscription_id,
        amount_toman=amount_toman,
        payment_gateway=payment_gateway,
        transaction_ref_id=transaction_ref_id,
        status=status
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


async def get_payment_by_id(db: AsyncSession, payment_id: int) -> Optional[Payment]:
    """Get payment by ID"""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalar_one_or_none()


async def update_payment_status(
    db: AsyncSession,
    payment_id: int,
    status: PaymentStatus
) -> Optional[Payment]:
    """Update payment status"""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if payment:
        payment.status = status
        if status == PaymentStatus.completed:
            payment.paid_at = datetime.utcnow()
        await db.commit()
        await db.refresh(payment)
    return payment


async def get_subscription_by_id(db: AsyncSession, subscription_id: int) -> Optional[UserSubscription]:
    """Get subscription by ID"""
    result = await db.execute(
        select(UserSubscription).where(UserSubscription.id == subscription_id)
    )
    return result.scalar_one_or_none()
