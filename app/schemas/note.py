from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class NoteBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    notebook_id: int
    session_date: Optional[str] = None  # Jalali date format: YYYY/MM/DD


class NoteCreate(NoteBase):
    pass


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    note: Optional[str] = None  # HTML content to update user_edited_text
    session_date: Optional[str] = None  # Jalali date format: YYYY/MM/DD


class NoteResponse(BaseModel):
    id: int
    notebook_id: int
    user_id: int
    title: str
    session_date: Optional[str] = None  # Jalali date format: YYYY/MM/DD
    note: Optional[str] = None  # HTML content from user_edited_text or gemini_output_text
    status: str

    # Error handling fields
    error_message: Optional[str] = None  # User-friendly error message in Persian
    retry_count: int = 0  # Number of retry attempts
    last_error_at: Optional[datetime] = None  # When the last error occurred

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db_model(cls, db_note):
        """Convert database model to response schema"""
        # Always use user_edited_text (this is the user's working copy)
        # Fallback to gemini_output_text only if user_edited_text is NULL
        note_content = db_note.user_edited_text if db_note.user_edited_text is not None else db_note.gemini_output_text

        return cls(
            id=db_note.id,
            notebook_id=db_note.notebook_id,
            user_id=db_note.user_id,
            title=db_note.title,
            session_date=db_note.session_date,
            note=note_content,
            status=db_note.status.value if hasattr(db_note.status, 'value') else db_note.status,
            error_message=db_note.error_message,
            retry_count=db_note.retry_count or 0,
            last_error_at=db_note.last_error_at,
            created_at=db_note.created_at,
            updated_at=db_note.updated_at
        )

    class Config:
        from_attributes = True


class NoteListResponse(BaseModel):
    id: int
    notebook_id: int
    user_id: int
    title: str
    session_date: Optional[str] = None  # Jalali date format: YYYY/MM/DD
    status: str
    user_edited_text: Optional[str] = None  # For preview in list view

    # Error handling fields (for list view)
    error_message: Optional[str] = None
    retry_count: int = 0

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    id: int
    note_id: int
    original_file_name: str
    storage_path: str
    file_type: str
    file_size_bytes: int
    created_at: datetime

    class Config:
        from_attributes = True
