"""
Queue Management API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.core.dependencies import get_current_user_from_cookie
from app.db.models import User
from app.services.queue_service import queue_manager, QueueError, RateLimitExceededError

router = APIRouter()


class QueueStatusResponse(BaseModel):
    queue_length: int
    processing_count: int
    capacity: int
    available_slots: int
    waiting_count: int
    processing_db_count: int
    completed_count: int
    failed_count: int


class NoteQueueStatusResponse(BaseModel):
    note_id: int
    status: str
    priority: int
    position: int
    estimated_wait_minutes: int


@router.get("/status", response_model=QueueStatusResponse)
async def get_queue_status(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت وضعیت کلی صف پردازش

    Returns:
        آمار کلی صف پردازش
    """
    try:
        stats = await queue_manager.get_queue_stats(db)
        return QueueStatusResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت وضعیت صف: {str(e)}"
        )


@router.get("/note/{note_id}", response_model=NoteQueueStatusResponse)
async def get_note_queue_status(
    note_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت وضعیت یک یادداشت در صف

    Args:
        note_id: شناسه یادداشت

    Returns:
        وضعیت یادداشت در صف
    """
    try:
        from sqlalchemy import select
        from app.db.models import ProcessingQueue

        # Get queue entry
        result = await db.execute(
            select(ProcessingQueue).where(ProcessingQueue.note_id == note_id)
        )
        queue_entry = result.scalar_one_or_none()

        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="یادداشت در صف یافت نشد"
            )

        # Check ownership
        if queue_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="دسترسی غیرمجاز"
            )

        # Get position
        position = await queue_manager.get_queue_position(note_id)

        return NoteQueueStatusResponse(
            note_id=note_id,
            status=queue_entry.status.value,
            priority=queue_entry.priority,
            position=position if position > 0 else 0,
            estimated_wait_minutes=max(0, position * 2)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت وضعیت: {str(e)}"
        )
