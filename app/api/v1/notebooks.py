from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.notebook import NotebookCreate, NotebookUpdate, NotebookResponse
from app.crud import notebook as notebook_crud
from app.core.dependencies import get_current_user_from_cookie
from app.db.models import User
from typing import List

router = APIRouter()


@router.post("/", response_model=NotebookResponse, status_code=status.HTTP_201_CREATED)
async def create_notebook(
    notebook: NotebookCreate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Create a new notebook"""
    db_notebook = await notebook_crud.create_notebook(db, notebook, current_user.id)

    # Get notes count
    notes_count = await notebook_crud.get_notebook_notes_count(db, db_notebook.id)

    response = NotebookResponse.model_validate(db_notebook)
    response.notes_count = notes_count
    return response


@router.get("/", response_model=List[NotebookResponse])
async def get_notebooks(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Get all notebooks for current user"""
    notebooks = await notebook_crud.get_notebooks_by_user(db, current_user.id)

    # Add notes count to each notebook
    result = []
    for notebook in notebooks:
        notes_count = await notebook_crud.get_notebook_notes_count(db, notebook.id)
        notebook_response = NotebookResponse.model_validate(notebook)
        notebook_response.notes_count = notes_count
        result.append(notebook_response)

    return result


@router.get("/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(
    notebook_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific notebook"""
    notebook = await notebook_crud.get_notebook_by_id(db, notebook_id, current_user.id)
    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found"
        )

    notes_count = await notebook_crud.get_notebook_notes_count(db, notebook.id)
    response = NotebookResponse.model_validate(notebook)
    response.notes_count = notes_count
    return response


@router.put("/{notebook_id}", response_model=NotebookResponse)
async def update_notebook(
    notebook_id: int,
    notebook_update: NotebookUpdate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Update a notebook"""
    notebook = await notebook_crud.update_notebook(
        db, notebook_id, current_user.id, notebook_update
    )
    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found"
        )

    notes_count = await notebook_crud.get_notebook_notes_count(db, notebook.id)
    response = NotebookResponse.model_validate(notebook)
    response.notes_count = notes_count
    return response


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook(
    notebook_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Delete a notebook"""
    success = await notebook_crud.delete_notebook(db, notebook_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found"
        )
    return None
