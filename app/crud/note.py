from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, case
from app.db.models import Note, Upload, NoteStatus
from app.schemas.note import NoteCreate, NoteUpdate
from typing import List, Optional
import re


def has_meaningful_content(html: str) -> bool:
    """
    Check if HTML has meaningful content beyond whitespace and empty tags.
    Returns False for content like: '', '<p></p>', '<p><br></p>', '<div></div>', etc.
    """
    if not html:
        return False

    # Remove all HTML tags
    text_only = re.sub(r'<[^>]+>', '', html)
    text_only = text_only.strip()

    # Check if there's actual text (more than 0 characters)
    return len(text_only) > 0


async def create_note(
    db: AsyncSession,
    note: NoteCreate,
    user_id: int,
    status: NoteStatus = NoteStatus.processing
) -> Note:
    """Create a new note"""
    db_note = Note(
        notebook_id=note.notebook_id,
        user_id=user_id,
        title=note.title,
        session_date=note.session_date,
        status=status
    )
    db.add(db_note)
    await db.commit()
    await db.refresh(db_note)
    return db_note


async def get_notes_by_user(
    db: AsyncSession,
    user_id: int,
    notebook_id: Optional[int] = None,
    exclude_failed: bool = True
) -> List[Note]:
    """Get all notes for a user, optionally filtered by notebook (only active notes)"""
    query = select(Note).where(Note.user_id == user_id, Note.is_active == True)

    # Exclude failed notes by default (they should only appear in notifications)
    if exclude_failed:
        query = query.where(Note.status != NoteStatus.failed)

    if notebook_id:
        query = query.where(Note.notebook_id == notebook_id)

    # Sort by session_date descending (nulls last using CASE), then by created_at descending
    # MySQL doesn't support NULLS LAST, so we use CASE to put NULL values last
    query = query.order_by(
        case((Note.session_date.is_(None), 1), else_=0),
        Note.session_date.desc(),
        Note.created_at.desc()
    )

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_note_by_id(db: AsyncSession, note_id: int, user_id: int) -> Optional[Note]:
    """Get note by ID for a specific user (only active notes)"""
    result = await db.execute(
        select(Note)
        .where(Note.id == note_id, Note.user_id == user_id, Note.is_active == True)
    )
    return result.scalar_one_or_none()


async def update_note(
    db: AsyncSession,
    note_id: int,
    user_id: int,
    note_update: NoteUpdate
) -> Optional[Note]:
    """Update note"""
    db_note = await get_note_by_id(db, note_id, user_id)
    if not db_note:
        return None

    update_data = note_update.model_dump(exclude_unset=True)
    content_updated = False

    # Handle 'note' field - store HTML in user_edited_text
    # Only update if note is provided AND has meaningful content
    if 'note' in update_data:
        note_content = update_data.pop('note')
        # Only update if content has meaningful text (not just empty tags like <p><br></p>)
        if note_content is not None and has_meaningful_content(note_content):
            db_note.user_edited_text = note_content
            content_updated = True
        # If empty or only has empty HTML tags, do not update (keep existing content)

    # Update other fields (title, session_date, etc.)
    for field, value in update_data.items():
        setattr(db_note, field, value)

    await db.commit()
    await db.refresh(db_note)

    # Re-index for RAG if content was updated
    if content_updated:
        try:
            from app.services.vector_service import index_note as index_note_for_rag
            content = db_note.user_edited_text or db_note.gemini_output_text
            if content:
                index_note_for_rag(
                    notebook_id=db_note.notebook_id,
                    note_id=db_note.id,
                    title=db_note.title,
                    html_content=content
                )
        except Exception as e:
            # Don't fail the update if indexing fails
            print(f"[NOTE CRUD] Warning: Failed to re-index note {note_id}: {e}")

    return db_note


async def delete_note(db: AsyncSession, note_id: int, user_id: int) -> bool:
    """Soft delete note by setting is_active to False"""
    db_note = await get_note_by_id(db, note_id, user_id)
    if not db_note:
        return False

    notebook_id = db_note.notebook_id

    db_note.is_active = False
    await db.commit()

    # Remove from RAG index
    try:
        from app.services.vector_service import delete_note_from_index
        delete_note_from_index(notebook_id, note_id)
    except Exception as e:
        # Don't fail the delete if index removal fails
        print(f"[NOTE CRUD] Warning: Failed to remove note {note_id} from index: {e}")

    return True


async def update_note_with_gemini_output(
    db: AsyncSession,
    note_id: int,
    status: NoteStatus,
    title: str,
    note_html: str
) -> Optional[Note]:
    """
    Update note with Gemini output
    
    Args:
        note_id: Note ID
        status: New status
        title: Extracted from Gemini JSON
        note_html: HTML note content from Gemini JSON
    """
    result = await db.execute(select(Note).where(Note.id == note_id))
    db_note = result.scalar_one_or_none()
    if not db_note:
        return None

    db_note.status = status
    db_note.title = title  # Update title from Gemini
    db_note.gemini_output_text = note_html  # Store HTML as backup/reference
    db_note.user_edited_text = note_html  # Initialize with Gemini output for user to edit

    await db.commit()
    await db.refresh(db_note)
    return db_note


async def create_upload(
    db: AsyncSession,
    note_id: int,
    user_id: int,
    original_file_name: str,
    storage_path: str,
    file_type: str,
    file_size_bytes: int,
    duration_seconds: Optional[int] = None
) -> Upload:
    """Create upload record"""
    db_upload = Upload(
        note_id=note_id,
        user_id=user_id,
        original_file_name=original_file_name,
        storage_path=storage_path,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        duration_seconds=duration_seconds
    )
    db.add(db_upload)
    await db.commit()
    await db.refresh(db_upload)
    return db_upload


async def get_uploads_by_note(db: AsyncSession, note_id: int) -> List[Upload]:
    """Get all uploads for a note"""
    result = await db.execute(
        select(Upload).where(Upload.note_id == note_id)
    )
    return list(result.scalars().all())


async def get_notes_by_notebook(db: AsyncSession, notebook_id: int, user_id: int) -> List[Note]:
    """Get all notes in a notebook (only active notes)"""
    result = await db.execute(
        select(Note)
        .where(Note.notebook_id == notebook_id, Note.user_id == user_id, Note.is_active == True)
        .order_by(Note.created_at.desc())
    )
    return list(result.scalars().all())
