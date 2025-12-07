from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class NotificationResponse(BaseModel):
    """Response schema for notification"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    message: str
    is_read: bool
    related_note_id: Optional[int]
    created_at: datetime


class UnreadCountResponse(BaseModel):
    """Response schema for unread notification count"""
    unread_count: int


class MarkAsReadRequest(BaseModel):
    """Request to mark notification(s) as read"""
    notification_ids: Optional[list[int]] = None  # If None, mark all as read
