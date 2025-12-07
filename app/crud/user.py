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
