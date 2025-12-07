from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.notification import NotificationResponse, UnreadCountResponse
from app.crud import notification as notification_crud
from app.core.dependencies import get_current_user_from_cookie
from app.db.models import User
from typing import List

router = APIRouter()


@router.get("/", response_model=List[NotificationResponse])
async def get_notifications(
    unread_only: bool = Query(False, description="فقط نوتیفیکیشن‌های خوانده نشده"),
    limit: int = Query(50, le=100, description="تعداد نوتیفیکیشن‌ها"),
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت لیست نوتیفیکیشن‌های کاربر
    """
    notifications = await notification_crud.get_user_notifications(
        db, current_user.id, unread_only, limit
    )
    return notifications


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت تعداد نوتیفیکیشن‌های خوانده نشده
    """
    count = await notification_crud.get_unread_count(db, current_user.id)
    return {"unread_count": count}


@router.put("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    علامت‌زدن یک نوتیفیکیشن به عنوان خوانده شده
    """
    success = await notification_crud.mark_notification_as_read(
        db, notification_id, current_user.id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    return {"message": "Notification marked as read"}


@router.put("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_as_read(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    علامت‌زدن همه نوتیفیکیشن‌ها به عنوان خوانده شده
    """
    count = await notification_crud.mark_all_notifications_as_read(
        db, current_user.id
    )
    return {"message": f"{count} notifications marked as read"}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    حذف یک نوتیفیکیشن
    """
    success = await notification_crud.delete_notification(
        db, notification_id, current_user.id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    return None
