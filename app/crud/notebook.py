from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.models import Notebook, Note, NoteStatus
from app.schemas.notebook import NotebookCreate, NotebookUpdate
from typing import List, Optional


async def create_notebook(db: AsyncSession, notebook: NotebookCreate, user_id: int) -> Notebook:
    """Create a new notebook"""
    db_notebook = Notebook(
        user_id=user_id,
        title=notebook.title
    )
    db.add(db_notebook)
    await db.commit()
    await db.refresh(db_notebook)
    return db_notebook


async def get_notebooks_by_user(db: AsyncSession, user_id: int) -> List[Notebook]:
    """Get all notebooks for a user"""
    result = await db.execute(
        select(Notebook)
        .where(Notebook.user_id == user_id)
        .order_by(Notebook.created_at.desc())
    )
    return list(result.scalars().all())


async def get_notebook_by_id(db: AsyncSession, notebook_id: int, user_id: int) -> Optional[Notebook]:
    """Get notebook by ID for a specific user"""
    result = await db.execute(
        select(Notebook)
        .where(Notebook.id == notebook_id, Notebook.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_notebook(
    db: AsyncSession,
    notebook_id: int,
    user_id: int,
    notebook_update: NotebookUpdate
) -> Optional[Notebook]:
    """Update notebook"""
    db_notebook = await get_notebook_by_id(db, notebook_id, user_id)
    if not db_notebook:
        return None

    update_data = notebook_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_notebook, field, value)

    await db.commit()
    await db.refresh(db_notebook)
    return db_notebook


async def delete_notebook(db: AsyncSession, notebook_id: int, user_id: int) -> bool:
    """Delete notebook"""
    db_notebook = await get_notebook_by_id(db, notebook_id, user_id)
    if not db_notebook:
        return False

    # Delete RAG index for this notebook
    try:
        from app.services.vector_service import delete_notebook_index
        delete_notebook_index(notebook_id)
    except Exception as e:
        # Don't fail the delete if index removal fails
        print(f"[NOTEBOOK CRUD] Warning: Failed to delete notebook {notebook_id} index: {e}")

    await db.delete(db_notebook)
    await db.commit()
    return True


async def get_notebook_notes_count(db: AsyncSession, notebook_id: int) -> int:
    """Get count of active, non-failed notes in a notebook"""
    result = await db.execute(
        select(func.count(Note.id)).where(
            Note.notebook_id == notebook_id,
            Note.is_active == True,
            Note.status != NoteStatus.failed
        )
    )
    return result.scalar() or 0
