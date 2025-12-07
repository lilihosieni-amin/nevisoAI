"""
CRUD operations برای چت
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.db.models import ChatSession, ChatMessage, Notebook


async def get_session_by_notebook(db: AsyncSession, notebook_id: int) -> Optional[ChatSession]:
    """دریافت session چت برای یک دفتر"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.notebook_id == notebook_id)
        .options(selectinload(ChatSession.messages))
    )
    return result.scalar_one_or_none()


async def get_or_create_session(db: AsyncSession, notebook_id: int, user_id: int) -> ChatSession:
    """دریافت یا ایجاد session چت"""
    session = await get_session_by_notebook(db, notebook_id)

    if session is None:
        session = ChatSession(
            notebook_id=notebook_id,
            user_id=user_id
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        # Load messages relationship
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.id == session.id)
            .options(selectinload(ChatSession.messages))
        )
        session = result.scalar_one()

    return session


async def add_message(db: AsyncSession, session_id: int, role: str, content: str) -> ChatMessage:
    """اضافه کردن پیام جدید"""
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def get_messages(db: AsyncSession, session_id: int, limit: int = 50) -> List[ChatMessage]:
    """دریافت پیام‌های یک session"""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_recent_messages_for_context(db: AsyncSession, session_id: int, limit: int = 10) -> List[dict]:
    """
    دریافت پیام‌های اخیر برای context به Gemini
    فرمت: [{"role": "user", "parts": ["text"]}, ...]
    """
    messages = await get_messages(db, session_id, limit)

    formatted = []
    for msg in messages:
        formatted.append({
            "role": msg.role,
            "parts": [msg.content]
        })

    return formatted


async def clear_session_messages(db: AsyncSession, session_id: int) -> int:
    """پاک کردن همه پیام‌های یک session"""
    result = await db.execute(
        delete(ChatMessage).where(ChatMessage.session_id == session_id)
    )
    await db.commit()
    return result.rowcount


async def delete_session(db: AsyncSession, notebook_id: int) -> bool:
    """حذف کامل session یک دفتر"""
    result = await db.execute(
        delete(ChatSession).where(ChatSession.notebook_id == notebook_id)
    )
    await db.commit()
    return result.rowcount > 0


async def get_notebook_for_chat(db: AsyncSession, notebook_id: int, user_id: int) -> Optional[Notebook]:
    """دریافت دفتر برای بررسی دسترسی"""
    result = await db.execute(
        select(Notebook)
        .where(Notebook.id == notebook_id)
        .where(Notebook.user_id == user_id)
    )
    return result.scalar_one_or_none()
