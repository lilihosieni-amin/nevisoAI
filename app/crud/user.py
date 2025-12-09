from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import User, UserOTP
from app.schemas.user import UserCreate, UserUpdate
from typing import Optional
from datetime import datetime


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_phone(db: AsyncSession, phone_number: str) -> Optional[User]:
    """Get user by phone number"""
    result = await db.execute(select(User).where(User.phone_number == phone_number))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email"""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user_by_email(db: AsyncSession, email: str) -> User:
    """Create a new user with email"""
    import hashlib
    # Create a short unique phone placeholder from email hash
    email_hash = hashlib.md5(email.encode()).hexdigest()[:12]
    db_user = User(email=email, phone_number=f"em_{email_hash}")
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def create_user(db: AsyncSession, user: UserCreate) -> User:
    """Create a new user"""
    db_user = User(phone_number=user.phone_number)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def update_user(db: AsyncSession, user_id: int, user_update: UserUpdate) -> Optional[User]:
    """Update user information"""
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        return None

    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)

    await db.commit()
    await db.refresh(db_user)
    return db_user


async def create_otp(db: AsyncSession, user_id: int, otp_code: str, expires_at: datetime) -> UserOTP:
    """Create OTP record"""
    db_otp = UserOTP(
        user_id=user_id,
        otp_code=otp_code,
        expires_at=expires_at
    )
    db.add(db_otp)
    await db.commit()
    await db.refresh(db_otp)
    return db_otp


async def get_valid_otp(db: AsyncSession, user_id: int, otp_code: str) -> Optional[UserOTP]:
    """Get valid OTP for user"""
    result = await db.execute(
        select(UserOTP)
        .where(
            UserOTP.user_id == user_id,
            UserOTP.otp_code == otp_code,
            UserOTP.is_used == False,
            UserOTP.expires_at > datetime.utcnow()
        )
    )
    return result.scalar_one_or_none()


async def mark_otp_used(db: AsyncSession, otp_id: int):
    """Mark OTP as used"""
    result = await db.execute(select(UserOTP).where(UserOTP.id == otp_id))
    db_otp = result.scalar_one_or_none()
    if db_otp:
        db_otp.is_used = True
        await db.commit()


async def grant_welcome_credit(db: AsyncSession, user_id: int) -> bool:
    """
    Grant 60 minutes of welcome credit to a new user

    Args:
        db: Database session
        user_id: User ID

    Returns:
        True if successful
    """
    from app.db.models import Plan, UserSubscription, SubscriptionStatus, CreditTransaction, TransactionType
    from datetime import datetime, timedelta

    print(f"[WELCOME CREDIT] Starting to grant welcome credit to user {user_id}")

    try:
        # Check if user already has any subscriptions (to avoid duplicate welcome credits)
        existing_subs = await db.execute(
            select(UserSubscription).where(UserSubscription.user_id == user_id)
        )
        if existing_subs.scalar_one_or_none():
            print(f"[WELCOME CREDIT] User {user_id} already has subscriptions, skipping")
            return False  # User already has subscriptions, skip welcome credit

        print(f"[WELCOME CREDIT] User {user_id} has no subscriptions, proceeding...")

        # Get or create "Welcome Bonus" plan
        WELCOME_PLAN_NAME = "هدیه خوش‌آمدگویی"
        result = await db.execute(
            select(Plan).where(Plan.name == WELCOME_PLAN_NAME)
        )
        welcome_plan = result.scalar_one_or_none()

        if not welcome_plan:
            print(f"[WELCOME CREDIT] Creating new welcome plan")
            # Create welcome bonus plan
            welcome_plan = Plan(
                name=WELCOME_PLAN_NAME,
                price_toman=0,  # Free
                duration_days=365,  # Valid for 1 year
                max_minutes=60,  # 60 minutes credit
                max_notebooks=10,  # Reasonable limit
                is_active=True,
                features={"type": "welcome_bonus", "description": "اعتبار رایگان خوش‌آمدگویی"}
            )
            db.add(welcome_plan)
            await db.flush()  # Get the plan ID without committing
            print(f"[WELCOME CREDIT] Welcome plan created with ID: {welcome_plan.id}")
        else:
            print(f"[WELCOME CREDIT] Using existing welcome plan ID: {welcome_plan.id}")

        # Create subscription for the user
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=365)

        subscription = UserSubscription(
            user_id=user_id,
            plan_id=welcome_plan.id,
            start_date=start_date,
            end_date=end_date,
            minutes_consumed=0,
            status=SubscriptionStatus.active
        )
        db.add(subscription)
        await db.flush()  # Get subscription ID
        print(f"[WELCOME CREDIT] Created subscription ID: {subscription.id} for user {user_id}")

        # Log the bonus transaction
        transaction = CreditTransaction(
            user_id=user_id,
            subscription_id=subscription.id,
            transaction_type=TransactionType.bonus,
            amount=60.0,
            balance_before=0.0,
            balance_after=60.0,
            description="اعتبار رایگان خوش‌آمدگویی برای کاربر جدید"
        )
        db.add(transaction)
        print(f"[WELCOME CREDIT] Created transaction for user {user_id}")

        await db.commit()
        print(f"[WELCOME CREDIT] Successfully granted 60 minutes to user {user_id}")
        return True

    except Exception as e:
        await db.rollback()
        print(f"[WELCOME CREDIT] Error granting welcome credit to user {user_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
