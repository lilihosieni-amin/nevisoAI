"""
API endpoints برای چت با دفتر
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.core.dependencies import get_current_user_from_cookie
from app.db.models import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatHistoryResponse,
    ChatResponse,
    ChatClearResponse,
    NotebookIndexStatus
)
from app.crud import chat as chat_crud
from app.crud import notebook as notebook_crud
from app.services.rag_service import chat_with_notebook, format_chat_history_for_gemini
from app.services.vector_service import get_notebook_stats

router = APIRouter()


async def verify_notebook_access(notebook_id: int, user: User, db: AsyncSession):
    """بررسی دسترسی کاربر به دفتر"""
    notebook = await chat_crud.get_notebook_for_chat(db, notebook_id, user.id)
    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دفتر یافت نشد"
        )
    return notebook


@router.post("/{notebook_id}/chat", response_model=ChatResponse)
async def send_chat_message(
    notebook_id: int,
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    ارسال پیام به چت دفتر و دریافت پاسخ
    """
    # بررسی دسترسی
    notebook = await verify_notebook_access(notebook_id, current_user, db)

    # دریافت یا ایجاد session
    session = await chat_crud.get_or_create_session(db, notebook_id, current_user.id)

    # دریافت history برای context
    chat_history = await chat_crud.get_recent_messages_for_context(db, session.id)
    print(f"[CHAT API] Chat history ({len(chat_history)} messages): {chat_history}")

    # ذخیره پیام کاربر
    user_message = await chat_crud.add_message(db, session.id, "user", message_data.message)

    try:
        # دریافت پاسخ از RAG
        ai_response = await chat_with_notebook(
            notebook_id=notebook_id,
            user_query=message_data.message,
            chat_history=chat_history
        )

        # ذخیره پاسخ AI
        assistant_message = await chat_crud.add_message(db, session.id, "model", ai_response)

        return ChatResponse(
            user_message=ChatMessageResponse.model_validate(user_message),
            assistant_message=ChatMessageResponse.model_validate(assistant_message)
        )

    except Exception as e:
        # در صورت خطا، پیام خطا ذخیره نمی‌شود ولی پیام کاربر باقی می‌ماند
        print(f"[CHAT API] Error processing message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در پردازش پیام: {str(e)}"
        )


@router.get("/{notebook_id}/chat", response_model=ChatHistoryResponse)
async def get_chat_history(
    notebook_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت تاریخچه چت دفتر
    """
    # بررسی دسترسی
    notebook = await verify_notebook_access(notebook_id, current_user, db)

    # دریافت session
    session = await chat_crud.get_session_by_notebook(db, notebook_id)

    messages = []
    if session:
        messages = [
            ChatMessageResponse.model_validate(msg)
            for msg in session.messages
        ]

    return ChatHistoryResponse(
        notebook_id=notebook_id,
        notebook_title=notebook.title,
        messages=messages,
        total_messages=len(messages)
    )


@router.delete("/{notebook_id}/chat", response_model=ChatClearResponse)
async def clear_chat(
    notebook_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    پاک کردن تاریخچه چت و شروع از اول
    """
    # بررسی دسترسی
    await verify_notebook_access(notebook_id, current_user, db)

    # دریافت session
    session = await chat_crud.get_session_by_notebook(db, notebook_id)

    if session:
        deleted_count = await chat_crud.clear_session_messages(db, session.id)
        return ChatClearResponse(
            success=True,
            message=f"{deleted_count} پیام پاک شد"
        )

    return ChatClearResponse(
        success=True,
        message="چتی برای پاک کردن وجود نداشت"
    )


@router.get("/{notebook_id}/chat/status", response_model=NotebookIndexStatus)
async def get_index_status(
    notebook_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    وضعیت ایندکس دفتر برای چت
    """
    # بررسی دسترسی
    await verify_notebook_access(notebook_id, current_user, db)

    stats = get_notebook_stats(notebook_id)

    return NotebookIndexStatus(
        notebook_id=notebook_id,
        total_chunks=stats.get("total_chunks", 0),
        is_indexed=stats.get("total_chunks", 0) > 0
    )
