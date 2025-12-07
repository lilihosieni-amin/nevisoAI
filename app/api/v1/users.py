from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.user import UserResponse, UserUpdate
from app.crud import user as user_crud
from app.crud import subscription as subscription_crud
from app.crud import plan as plan_crud
from app.core.dependencies import get_current_user_from_cookie
from app.db.models import User

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: User = Depends(get_current_user_from_cookie)
):
    """Get current user profile"""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Update current user profile"""
    updated_user = await user_crud.update_user(db, current_user.id, user_update)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.model_validate(updated_user)


@router.get("/me/subscription")
async def get_current_subscription(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's active subscription with plan details"""
    try:
        subscription = await subscription_crud.get_active_subscription(db, current_user.id)
        
        if not subscription:
            return {
                "has_subscription": False,
                "plan_name": "رایگان",
                "minutes_consumed": 0,
                "minutes_limit": 0
            }

        # Get plan details
        plan = await plan_crud.get_plan_by_id(db, subscription.plan_id)
        
        return {
            "has_subscription": True,
            "subscription_id": subscription.id,
            "plan_id": subscription.plan_id,
            "plan_name": plan.name if plan else "نامشخص",
            "start_date": subscription.start_date.isoformat(),
            "end_date": subscription.end_date.isoformat(),
            "minutes_consumed": subscription.minutes_consumed,
            "minutes_limit": plan.max_minutes if plan else 0,
            "status": subscription.status.value
        }
    except Exception as e:
        # Log the error and return a default response
        print(f"Error getting subscription: {e}")
        return {
            "has_subscription": False,
            "plan_name": "رایگان",
            "minutes_consumed": 0,
            "minutes_limit": 0
        }
