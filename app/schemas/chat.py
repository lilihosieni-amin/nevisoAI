"""
Pydantic schemas برای چت
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ChatMessageCreate(BaseModel):
    """Schema برای ارسال پیام جدید"""
    message: str = Field(..., min_length=1, max_length=4000, description="متن پیام")


class ChatMessageResponse(BaseModel):
    """Schema برای پاسخ پیام"""
    id: int
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """Schema برای تاریخچه چت"""
    notebook_id: int
    notebook_title: str
    messages: List[ChatMessageResponse]
    total_messages: int


class ChatResponse(BaseModel):
    """Schema برای پاسخ به پیام"""
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


class ChatClearResponse(BaseModel):
    """Schema برای پاسخ پاک کردن چت"""
    success: bool
    message: str


class NotebookIndexStatus(BaseModel):
    """Schema برای وضعیت ایندکس دفتر"""
    notebook_id: int
    total_chunks: int
    is_indexed: bool
