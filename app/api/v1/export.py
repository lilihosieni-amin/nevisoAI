from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.crud import note as note_crud
from app.crud import notebook as notebook_crud
from app.core.dependencies import get_current_user_from_cookie
from app.db.models import User, NoteStatus
from app.services.pdf_service import generate_notebook_pdf
from urllib.parse import quote

router = APIRouter()


@router.get("/notebooks/{notebook_id}/pdf")
async def export_notebook_pdf(
    notebook_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Export all notes in a notebook as a single PDF"""
    # Verify notebook belongs to user
    notebook = await notebook_crud.get_notebook_by_id(db, notebook_id, current_user.id)
    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found"
        )

    # Get all completed notes in notebook
    notes = await note_crud.get_notes_by_notebook(db, notebook_id, current_user.id)
    completed_notes = [n for n in notes if n.status == NoteStatus.completed]

    if not completed_notes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No completed notes in this notebook"
        )

    # Sort notes by session_date (ascending - oldest first)
    # session_date format is YYYY/MM/DD (Jalali), so string sorting works correctly
    completed_notes.sort(key=lambda n: n.session_date or "")

    # Prepare notes data for PDF generation
    notes_data = []
    for note in completed_notes:
        content = note.user_edited_text or note.gemini_output_text
        if content:
            notes_data.append({
                "title": note.title,
                "session_date": note.session_date if note.session_date else None,  # Already a string (Jalali date)
                "content": content
            })

    # Generate PDF
    pdf_buffer = generate_notebook_pdf(notebook.title, notes_data)

    # Return PDF as streaming response
    filename = f"{notebook.title}.pdf"
    encoded_filename = quote(filename)

    headers = {
        'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
    }

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers=headers
    )