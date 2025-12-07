from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.note import NoteCreate, NoteUpdate, NoteResponse, NoteListResponse, UploadResponse
from app.crud import note as note_crud
from app.crud import notebook as notebook_crud
from app.core.dependencies import get_current_user_from_cookie
from app.core.config import settings
from app.db.models import User, NoteStatus
from app.worker.tasks_with_credits_fixed import process_file_with_credits
from app.services.pdf_service import generate_note_pdf, generate_notebook_pdf
from typing import List, Optional
import os
import uuid
import aiofiles
from urllib.parse import quote

router = APIRouter()


@router.post("/uploads/", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Upload a file (to be associated with a note later)"""
    # Create uploads directory if it doesn't exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)

    file_size = len(content)

    # For now, we'll return the upload info
    # The note will be created in a separate endpoint
    return {
        "id": 0,  # Temporary ID
        "note_id": 0,  # Will be set when note is created
        "original_file_name": file.filename,
        "storage_path": file_path,
        "file_type": file.content_type or "application/octet-stream",
        "file_size_bytes": file_size,
        "created_at": None
    }


@router.post("/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    title: str = Form(...),
    notebook_id: int = Form(...),
    session_date: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Create a note with multiple file uploads and trigger processing"""
    # Verify notebook belongs to user
    notebook = await notebook_crud.get_notebook_by_id(db, notebook_id, current_user.id)
    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found"
        )

    # Validate files (only audio and image)
    allowed_types = [
        'audio/', 'image/',
        'video/',  # برای ویس که به صورت ویدیو ذخیره میشه
        'application/octet-stream'  # بعضی مرورگرها این رو میفرستن
    ]

    for file in files:
        content_type = file.content_type or ''
        if not any(content_type.startswith(t) for t in allowed_types):
            # Check by extension if content_type not reliable
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ['.mp3', '.wav', '.m4a', '.ogg', '.webm', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"فایل {file.filename} فرمت مجاز نیست. فقط فایل‌های صوتی و تصویری مجاز هستند."
                )

    # Create note with Jalali date (no conversion needed)
    note_data = NoteCreate(
        title=title,
        notebook_id=notebook_id,
        session_date=session_date  # Store Jalali date as-is
    )

    db_note = await note_crud.create_note(db, note_data, current_user.id, NoteStatus.processing)

    # Save all uploaded files
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    for file in files:
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)

        file_size = len(content)

        # Create upload record for each file
        await note_crud.create_upload(
            db=db,
            note_id=db_note.id,
            user_id=current_user.id,
            original_file_name=file.filename,
            storage_path=file_path,
            file_type=file.content_type or "application/octet-stream",
            file_size_bytes=file_size
        )

    # Trigger background processing with credit management
    process_file_with_credits.delay(db_note.id)

    return NoteResponse.from_db_model(db_note)


@router.get("/", response_model=List[NoteListResponse])
async def get_notes(
    notebook_id: Optional[int] = None,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Get all notes for current user, optionally filtered by notebook"""
    notes = await note_crud.get_notes_by_user(db, current_user.id, notebook_id)
    return [NoteListResponse.model_validate(note) for note in notes]


@router.get("/{note_id}/debug")
async def get_note_debug(
    note_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Debug endpoint to check note content"""
    note = await note_crud.get_note_by_id(db, note_id, current_user.id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    return {
        "id": note.id,
        "title": note.title,
        "status": note.status.value if hasattr(note.status, 'value') else note.status,
        "has_gemini_output": note.gemini_output_text is not None,
        "has_user_edited": note.user_edited_text is not None,
        "gemini_length": len(note.gemini_output_text) if note.gemini_output_text else 0,
        "edited_length": len(note.user_edited_text) if note.user_edited_text else 0,
        "gemini_preview": note.gemini_output_text[:200] if note.gemini_output_text else None,
        "edited_preview": note.user_edited_text[:200] if note.user_edited_text else None,
        "note_content_that_would_be_returned": (note.user_edited_text if note.user_edited_text is not None else note.gemini_output_text)[:200] if (note.user_edited_text or note.gemini_output_text) else None
    }


@router.get("/{note_id}/raw")
async def get_note_raw(
    note_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Get raw note content without schema (for debugging frontend)"""
    note = await note_crud.get_note_by_id(db, note_id, current_user.id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    # Return exactly what NoteResponse.from_db_model would return
    note_content = note.user_edited_text if note.user_edited_text is not None else note.gemini_output_text

    return {
        "id": note.id,
        "title": note.title,
        "note": note_content,  # Full HTML content
        "status": note.status.value if hasattr(note.status, 'value') else note.status
    }


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific note with full content"""
    note = await note_crud.get_note_by_id(db, note_id, current_user.id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    # Prevent accessing notes that are still processing
    if note.status == NoteStatus.processing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Note is still being processed"
        )

    return NoteResponse.from_db_model(note)


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int,
    note_update: NoteUpdate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Update a note"""
    note = await note_crud.update_note(db, note_id, current_user.id, note_update)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    return NoteResponse.from_db_model(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Delete a note"""
    success = await note_crud.delete_note(db, note_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    return None


@router.get("/{note_id}/export/pdf")
async def export_note_pdf(
    note_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Export a single note as PDF"""
    note = await note_crud.get_note_by_id(db, note_id, current_user.id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    if note.status != NoteStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Note processing not completed yet"
        )

    # Use user_edited_text if available, otherwise use gemini_output_text
    content = note.user_edited_text or note.gemini_output_text
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Note has no content"
        )

    # Generate PDF
    pdf_buffer = generate_note_pdf(note.title, content, note.session_date)

    # Return PDF as streaming response
    filename = f"{note.title}.pdf"
    encoded_filename = quote(filename)
    
    headers = {
        'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
    }

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers=headers
    )