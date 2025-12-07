from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import Notification
from typing import List, Optional


async def get_user_notifications(
    db: AsyncSession,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50
) -> List[Notification]:
    """Get notifications for a user"""
    query = select(Notification).where(Notification.user_id == user_id)

    if unread_only:
        query = query.where(Notification.is_read == False)

    query = query.order_by(Notification.created_at.desc()).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def get_notification_by_id(
    db: AsyncSession,
    notification_id: int,
    user_id: int
) -> Optional[Notification]:
    """Get a specific notification"""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def mark_notification_as_read(
    db: AsyncSession,
    notification_id: int,
    user_id: int
) -> bool:
    """Mark a notification as read"""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id
        )
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount > 0


async def mark_all_notifications_as_read(
    db: AsyncSession,
    user_id: int
) -> int:
    """Mark all notifications as read for a user"""
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount


async def get_unread_count(
    db: AsyncSession,
    user_id: int
) -> int:
    """Get count of unread notifications"""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False
        )
    )
    return len(result.scalars().all())


async def delete_notification(
    db: AsyncSession,
    notification_id: int,
    user_id: int
) -> bool:
    """Delete a notification"""
    notification = await get_notification_by_id(db, notification_id, user_id)
    if notification:
        await db.delete(notification)
        await db.commit()
        return True
    return False
