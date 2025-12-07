from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class NotebookBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class NotebookCreate(NotebookBase):
    pass


class NotebookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)


class NotebookResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    notes_count: Optional[int] = 0

    class Config:
        from_attributes = True
