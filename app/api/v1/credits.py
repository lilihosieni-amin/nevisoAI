"""
Credit Management API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.core.dependencies import get_current_user_from_cookie
from app.db.models import User
from app.services.credit_service import credit_manager, InsufficientCreditsError

router = APIRouter()


class CreditBalanceResponse(BaseModel):
    total_minutes: float
    subscriptions: List[dict]


class CreditTransactionResponse(BaseModel):
    id: int
    type: str
    amount: float
    balance_before: float
    balance_after: float
    description: Optional[str]
    note_id: Optional[int]
    subscription_id: Optional[int]
    created_at: str


@router.get("/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت موجودی اعتبار کاربر

    Returns:
        - total_minutes: مجموع اعتبار موجود (دقیقه)
        - subscriptions: لیست اشتراک‌های فعال با جزئیات
    """
    try:
        balance = await credit_manager.get_user_balance(db, current_user.id)
        return CreditBalanceResponse(**balance)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت موجودی: {str(e)}"
        )


@router.get("/transactions", response_model=List[CreditTransactionResponse])
async def get_credit_transactions(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت تاریخچه تراکنش‌های اعتبار

    Args:
        limit: تعداد رکورد (پیش‌فرض: 50)
        offset: شروع از رکورد (برای صفحه‌بندی)

    Returns:
        لیست تراکنش‌ها
    """
    try:
        transactions = await credit_manager.get_user_transactions(
            db,
            current_user.id,
            limit=limit,
            offset=offset
        )
        return [CreditTransactionResponse(**t) for t in transactions]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت تاریخچه: {str(e)}"
        )


@router.get("/check/{note_id}")
async def check_required_credits(
    note_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    محاسبه اعتبار مورد نیاز برای یک یادداشت

    Args:
        note_id: شناسه یادداشت

    Returns:
        اعتبار مورد نیاز و موجودی فعلی
    """
    try:
        # Calculate required credits
        required = await credit_manager.calculate_note_credits(db, note_id)

        # Get current balance
        balance = await credit_manager.get_user_balance(db, current_user.id)

        return {
            'required_minutes': required,
            'current_balance': balance['total_minutes'],
            'is_sufficient': balance['total_minutes'] >= required
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در محاسبه اعتبار: {str(e)}"
        )
