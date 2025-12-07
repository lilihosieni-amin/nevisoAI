# برنامه پیاده‌سازی چت RAG برای دفترها

## خلاصه پروژه
اضافه کردن قابلیت چت با هوش مصنوعی به هر دفتر. کاربر می‌تواند با AI درباره محتوای جزوات دفتر گفتگو کند. سیستم از RAG (Retrieval Augmented Generation) با Vector Database استفاده می‌کند.

### ویژگی‌ها
- چت در سطح دفتر (AI از تمام جزوات دفتر استفاده می‌کند)
- جستجوی معنایی با ChromaDB
- پشتیبانی از فارسی و انگلیسی
- امکان پاک کردن چت و شروع از اول
- نمایش آخرین چت (بدون تاریخچه چت‌های قبلی)
- فعلاً رایگان (بدون کسر اعتبار)

---

## فاز ۱: نصب Dependencies و تنظیمات اولیه

### ۱.۱ اضافه کردن به `requirements.txt`
```txt
chromadb==0.4.22
sentence-transformers==2.2.2
```

### ۱.۲ تنظیمات در `app/core/config.py`
```python
# ChromaDB Settings
CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"
EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RAG_TOP_K: int = 5  # تعداد chunks مرتبط برای context
RAG_CHUNK_SIZE: int = 500  # اندازه هر chunk (تعداد کاراکتر)
RAG_CHUNK_OVERLAP: int = 50  # overlap بین chunks
```

### ۱.۳ ایجاد پوشه ChromaDB
```bash
mkdir -p ./chroma_db
```

---

## فاز ۲: سرویس Embedding

### ۲.۱ فایل جدید: `app/services/embedding_service.py`

```python
"""
سرویس تولید Embedding برای متون فارسی/انگلیسی
"""
from sentence_transformers import SentenceTransformer
from typing import List
import re
from bs4 import BeautifulSoup
from app.core.config import settings

# Load model once at startup
_model = None

def get_embedding_model() -> SentenceTransformer:
    """Lazy load embedding model"""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def generate_embedding(text: str) -> List[float]:
    """
    تولید embedding vector برای یک متن

    Args:
        text: متن ورودی

    Returns:
        لیست اعداد float (vector)
    """
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    تولید embedding برای چند متن (batch processing)

    Args:
        texts: لیست متون

    Returns:
        لیست از vectors
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


def clean_html(html_content: str) -> str:
    """
    حذف تگ‌های HTML و استخراج متن خالص

    Args:
        html_content: محتوای HTML

    Returns:
        متن خالص
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'html.parser')

    # حذف script و style
    for tag in soup(['script', 'style']):
        tag.decompose()

    text = soup.get_text(separator=' ')

    # پاکسازی فضاهای اضافی
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
    """
    تکه‌تکه کردن متن به chunks با overlap

    Args:
        text: متن ورودی
        chunk_size: اندازه هر chunk (پیش‌فرض از settings)
        overlap: میزان overlap (پیش‌فرض از settings)

    Returns:
        لیست chunks
    """
    if chunk_size is None:
        chunk_size = settings.RAG_CHUNK_SIZE
    if overlap is None:
        overlap = settings.RAG_CHUNK_OVERLAP

    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # سعی کن در پایان جمله یا کلمه تمام کنی
        if end < len(text):
            # پیدا کردن آخرین نقطه یا فاصله
            last_period = chunk.rfind('.')
            last_space = chunk.rfind(' ')

            if last_period > chunk_size * 0.7:
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1
            elif last_space > chunk_size * 0.7:
                chunk = chunk[:last_space]
                end = start + last_space

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if c]  # حذف chunks خالی


def prepare_note_for_indexing(note_id: int, title: str, html_content: str) -> List[dict]:
    """
    آماده‌سازی یک جزوه برای ایندکس شدن

    Args:
        note_id: شناسه جزوه
        title: عنوان جزوه
        html_content: محتوای HTML

    Returns:
        لیست دیکشنری‌ها با id, text, metadata
    """
    clean_text = clean_html(html_content)

    # اضافه کردن عنوان به ابتدای متن
    full_text = f"{title}\n\n{clean_text}"

    chunks = chunk_text(full_text)

    documents = []
    for i, chunk in enumerate(chunks):
        documents.append({
            "id": f"note_{note_id}_chunk_{i}",
            "text": chunk,
            "metadata": {
                "note_id": note_id,
                "chunk_index": i,
                "title": title
            }
        })

    return documents
```

---

## فاز ۳: سرویس Vector Store (ChromaDB)

### ۳.۱ فایل جدید: `app/services/vector_service.py`

```python
"""
سرویس مدیریت Vector Database با ChromaDB
"""
import chromadb
from chromadb.config import Settings
from typing import List, Optional
from app.core.config import settings
from app.services.embedding_service import generate_embedding, generate_embeddings

# Initialize ChromaDB client
_client = None

def get_chroma_client() -> chromadb.Client:
    """Get or create ChromaDB client"""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIRECTORY,
            settings=Settings(anonymized_telemetry=False)
        )
    return _client


def get_notebook_collection(notebook_id: int):
    """
    دریافت یا ایجاد collection برای یک دفتر

    Args:
        notebook_id: شناسه دفتر

    Returns:
        ChromaDB Collection
    """
    client = get_chroma_client()
    collection_name = f"notebook_{notebook_id}"

    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}  # استفاده از cosine similarity
    )


def index_note(notebook_id: int, note_id: int, title: str, html_content: str) -> int:
    """
    ایندکس کردن یک جزوه در vector store

    Args:
        notebook_id: شناسه دفتر
        note_id: شناسه جزوه
        title: عنوان جزوه
        html_content: محتوای HTML جزوه

    Returns:
        تعداد chunks ایندکس شده
    """
    from app.services.embedding_service import prepare_note_for_indexing

    # اول chunks قبلی این جزوه رو حذف کن
    delete_note_from_index(notebook_id, note_id)

    # آماده‌سازی documents
    documents = prepare_note_for_indexing(note_id, title, html_content)

    if not documents:
        return 0

    collection = get_notebook_collection(notebook_id)

    # تولید embeddings
    texts = [doc["text"] for doc in documents]
    embeddings = generate_embeddings(texts)

    # اضافه کردن به collection
    collection.add(
        ids=[doc["id"] for doc in documents],
        embeddings=embeddings,
        documents=texts,
        metadatas=[doc["metadata"] for doc in documents]
    )

    return len(documents)


def delete_note_from_index(notebook_id: int, note_id: int) -> bool:
    """
    حذف یک جزوه از ایندکس

    Args:
        notebook_id: شناسه دفتر
        note_id: شناسه جزوه

    Returns:
        True در صورت موفقیت
    """
    try:
        collection = get_notebook_collection(notebook_id)

        # پیدا کردن همه chunks این جزوه
        results = collection.get(
            where={"note_id": note_id}
        )

        if results["ids"]:
            collection.delete(ids=results["ids"])

        return True
    except Exception as e:
        print(f"Error deleting note {note_id} from index: {e}")
        return False


def delete_notebook_index(notebook_id: int) -> bool:
    """
    حذف کامل ایندکس یک دفتر

    Args:
        notebook_id: شناسه دفتر

    Returns:
        True در صورت موفقیت
    """
    try:
        client = get_chroma_client()
        collection_name = f"notebook_{notebook_id}"

        # بررسی وجود collection
        collections = client.list_collections()
        if any(c.name == collection_name for c in collections):
            client.delete_collection(collection_name)

        return True
    except Exception as e:
        print(f"Error deleting notebook {notebook_id} index: {e}")
        return False


def search(notebook_id: int, query: str, top_k: int = None) -> List[dict]:
    """
    جستجوی معنایی در جزوات یک دفتر

    Args:
        notebook_id: شناسه دفتر
        query: متن جستجو
        top_k: تعداد نتایج (پیش‌فرض از settings)

    Returns:
        لیست نتایج با text و metadata
    """
    if top_k is None:
        top_k = settings.RAG_TOP_K

    collection = get_notebook_collection(notebook_id)

    # بررسی خالی بودن collection
    if collection.count() == 0:
        return []

    # تولید embedding برای query
    query_embedding = generate_embedding(query)

    # جستجو
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count())
    )

    # فرمت کردن نتایج
    formatted_results = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            formatted_results.append({
                "text": doc,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None
            })

    return formatted_results


def get_notebook_stats(notebook_id: int) -> dict:
    """
    آمار ایندکس یک دفتر

    Args:
        notebook_id: شناسه دفتر

    Returns:
        دیکشنری با آمار
    """
    try:
        collection = get_notebook_collection(notebook_id)
        return {
            "total_chunks": collection.count(),
            "collection_name": f"notebook_{notebook_id}"
        }
    except:
        return {"total_chunks": 0, "collection_name": None}
```

---

## فاز ۴: مدل‌های دیتابیس

### ۴.۱ اضافه کردن به `app/db/models.py`

```python
class ChatSession(Base):
    """
    جلسه چت برای هر دفتر
    هر دفتر فقط یک session فعال دارد
    """
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    notebook = relationship("Notebook", back_populates="chat_session")
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    """
    پیام‌های چت
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
```

### ۴.۲ اضافه کردن relationship به مدل‌های موجود

در مدل `Notebook`:
```python
# اضافه کردن به relationships
chat_session = relationship("ChatSession", back_populates="notebook", uselist=False, cascade="all, delete-orphan")
```

در مدل `User`:
```python
# اضافه کردن به relationships
chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
```

### ۴.۳ ایجاد Migration

```bash
cd /home/lili/Desktop/DriveD/work/neviso/thirdTry/neviso-backend
alembic revision --autogenerate -m "add chat tables"
alembic upgrade head
```

**محتوای Migration:**
```python
def upgrade():
    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('notebook_id', sa.Integer(), sa.ForeignKey('notebooks.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index('ix_chat_sessions_notebook_id', 'chat_sessions', ['notebook_id'])
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])


def downgrade():
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
```

---

## فاز ۵: Schemas (Pydantic)

### ۵.۱ فایل جدید: `app/schemas/chat.py`

```python
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
```

---

## فاز ۶: CRUD Operations

### ۶.۱ فایل جدید: `app/crud/chat.py`

```python
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
    return result.scalars().all()


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


async def get_notebook_with_notes(db: AsyncSession, notebook_id: int, user_id: int) -> Optional[Notebook]:
    """دریافت دفتر با جزوات برای بررسی دسترسی"""
    result = await db.execute(
        select(Notebook)
        .where(Notebook.id == notebook_id)
        .where(Notebook.user_id == user_id)
    )
    return result.scalar_one_or_none()
```

---

## فاز ۷: سرویس RAG

### ۷.۱ فایل جدید: `app/services/rag_service.py`

```python
"""
سرویس RAG برای چت با دفتر
"""
import google.generativeai as genai
from typing import List, Optional
from app.core.config import settings
from app.services.vector_service import search as vector_search

# System instruction برای چت
CHAT_SYSTEM_INSTRUCTION = """شما یک دستیار هوشمند برای دانشجویان هستید.
وظیفه شما پاسخ به سوالات کاربر بر اساس محتوای جزوات درسی است.

### قوانین:
1. فقط بر اساس اطلاعات ارائه شده در "محتوای مرتبط" پاسخ دهید
2. اگر پاسخ در محتوا نیست، صادقانه بگویید "این اطلاعات در جزوات موجود نیست"
3. زبان پاسخ باید با زبان سوال یکسان باشد (فارسی یا انگلیسی)
4. پاسخ‌ها باید مختصر و مفید باشند
5. در صورت نیاز، از فرمت‌بندی (bullet points، شماره‌گذاری) استفاده کنید
6. اگر سوال مبهم است، برای روشن شدن سوال بپرسید

### محتوای مرتبط از جزوات:
{context}

### دستورالعمل:
به سوال کاربر بر اساس محتوای بالا پاسخ دهید. اگر اطلاعات کافی نیست، این موضوع را ذکر کنید.
"""


async def chat_with_notebook(
    notebook_id: int,
    user_query: str,
    chat_history: List[dict] = None
) -> str:
    """
    چت با یک دفتر با استفاده از RAG

    Args:
        notebook_id: شناسه دفتر
        user_query: سوال کاربر
        chat_history: تاریخچه چت قبلی (اختیاری)

    Returns:
        پاسخ AI
    """
    # ۱. جستجو در vector store
    relevant_chunks = vector_search(notebook_id, user_query)

    # ۲. ساخت context از chunks
    if relevant_chunks:
        context_parts = []
        for i, chunk in enumerate(relevant_chunks, 1):
            title = chunk.get("metadata", {}).get("title", "بدون عنوان")
            text = chunk.get("text", "")
            context_parts.append(f"[از جزوه: {title}]\n{text}")

        context = "\n\n---\n\n".join(context_parts)
    else:
        context = "هیچ محتوای مرتبطی یافت نشد."

    # ۳. ساخت system instruction با context
    system_instruction = CHAT_SYSTEM_INSTRUCTION.format(context=context)

    # ۴. ایجاد مدل
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system_instruction
    )

    # ۵. شروع چت با history
    chat = model.start_chat(history=chat_history or [])

    # ۶. ارسال پیام و دریافت پاسخ
    try:
        response = chat.send_message(user_query)
        return response.text
    except Exception as e:
        print(f"Error in RAG chat: {e}")
        raise


async def get_relevant_context(notebook_id: int, query: str) -> str:
    """
    فقط دریافت context مرتبط (بدون چت)
    برای debug یا نمایش به کاربر
    """
    chunks = vector_search(notebook_id, query)

    if not chunks:
        return "محتوای مرتبطی یافت نشد."

    parts = []
    for chunk in chunks:
        title = chunk.get("metadata", {}).get("title", "")
        text = chunk.get("text", "")
        parts.append(f"**{title}**\n{text}")

    return "\n\n---\n\n".join(parts)
```

---

## فاز ۸: API Endpoints

### ۸.۱ فایل جدید: `app/api/v1/chat.py`

```python
"""
API endpoints برای چت با دفتر
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.dependencies import get_current_user_from_cookie, get_db
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
from app.services.rag_service import chat_with_notebook
from app.services.vector_service import get_notebook_stats

router = APIRouter(prefix="/notebooks", tags=["chat"])


async def verify_notebook_access(notebook_id: int, user: User, db: AsyncSession):
    """بررسی دسترسی کاربر به دفتر"""
    notebook = await notebook_crud.get_notebook(db, notebook_id)
    if not notebook or notebook.user_id != user.id:
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
        assistant_message = await chat_crud.add_message(db, session.id, "assistant", ai_response)

        return ChatResponse(
            user_message=ChatMessageResponse.model_validate(user_message),
            assistant_message=ChatMessageResponse.model_validate(assistant_message)
        )

    except Exception as e:
        # در صورت خطا، پیام خطا ذخیره نمی‌شود ولی پیام کاربر باقی می‌ماند
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
```

### ۸.۲ ثبت Router در `app/main.py`

```python
from app.api.v1 import chat

# اضافه کردن به routers
app.include_router(chat.router, prefix="/api/v1")
```

---

## فاز ۹: Frontend - صفحه چت

### ۹.۱ Route جدید در `app/main.py`

```python
@app.get("/chat", response_class=HTMLResponse)
async def chat_page(
    request: Request,
    notebook_id: int,
    current_user: User = Depends(get_current_user_from_cookie_optional)
):
    """صفحه چت با دفتر"""
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "notebook_id": notebook_id,
            "user": current_user
        }
    )
```

### ۹.۲ فایل جدید: `app/templates/chat.html`

```html
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>گفتگو با دفتر - نویسو</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet">
    <link rel="stylesheet" href="/static/css/style.css">
    <style>
        .chat-container {
            display: flex;
            flex-direction: column;
            height: calc(100vh - 120px);
            max-width: 900px;
            margin: 0 auto;
            padding: 1rem;
        }

        .chat-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem;
            background: var(--bg-card);
            border-radius: 12px;
            margin-bottom: 1rem;
        }

        .chat-header-right {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .back-btn {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--text-secondary);
            text-decoration: none;
            transition: color 0.2s;
        }

        .back-btn:hover {
            color: var(--text-primary);
        }

        .notebook-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .clear-chat-btn {
            padding: 0.5rem 1rem;
            background: var(--bg-hover);
            border: none;
            border-radius: 8px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.2s;
        }

        .clear-chat-btn:hover {
            background: #fee2e2;
            color: #dc2626;
        }

        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .message {
            display: flex;
            gap: 0.75rem;
            max-width: 85%;
        }

        .message.user {
            align-self: flex-start;
            flex-direction: row;
        }

        .message.assistant {
            align-self: flex-end;
            flex-direction: row-reverse;
        }

        .message-avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            font-size: 1.25rem;
        }

        .message.user .message-avatar {
            background: var(--primary-light);
        }

        .message.assistant .message-avatar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }

        .message-content {
            padding: 0.75rem 1rem;
            border-radius: 12px;
            line-height: 1.6;
        }

        .message.user .message-content {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
        }

        .message.assistant .message-content {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .chat-input-container {
            display: flex;
            gap: 0.75rem;
            padding: 1rem;
            background: var(--bg-card);
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }

        .chat-input {
            flex: 1;
            padding: 0.75rem 1rem;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: inherit;
            font-size: 1rem;
            resize: none;
            max-height: 120px;
        }

        .chat-input:focus {
            outline: none;
            border-color: var(--primary-color);
        }

        .send-btn {
            padding: 0.75rem 1.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .send-btn:hover:not(:disabled) {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        .send-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--text-secondary);
            text-align: center;
        }

        .empty-state-icon {
            font-size: 4rem;
            margin-bottom: 1rem;
        }

        .empty-state-text {
            font-size: 1.1rem;
        }

        .loading-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1rem;
            background: var(--bg-card);
            border-radius: 12px;
            color: var(--text-secondary);
            align-self: flex-end;
        }

        .loading-dots {
            display: flex;
            gap: 4px;
        }

        .loading-dots span {
            width: 8px;
            height: 8px;
            background: var(--primary-color);
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }

        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }

        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }

        .not-indexed-warning {
            background: #fef3c7;
            border: 1px solid #f59e0b;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            color: #92400e;
            text-align: center;
        }
    </style>
</head>
<body data-theme="light">
    <div class="app-container">
        {% set active_page = 'chat' %}
        {% include 'components/sidebar.html' %}

        <main class="main-content-wrapper">
            <div class="chat-container">
                <!-- Header -->
                <div class="chat-header">
                    <div class="chat-header-right">
                        <a href="/notes?notebook_id={{ notebook_id }}" class="back-btn">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M9 18l6-6-6-6"/>
                            </svg>
                            بازگشت
                        </a>
                        <h1 class="notebook-title" id="notebook-title">در حال بارگذاری...</h1>
                    </div>
                    <button class="clear-chat-btn" onclick="clearChat()">
                        پاک کردن گفتگو
                    </button>
                </div>

                <!-- Warning for not indexed -->
                <div class="not-indexed-warning" id="not-indexed-warning" style="display: none;">
                    ⚠️ این دفتر هنوز ایندکس نشده است. لطفاً صبر کنید تا جزوات پردازش شوند.
                </div>

                <!-- Messages -->
                <div class="messages-container" id="messages-container">
                    <div class="empty-state" id="empty-state">
                        <div class="empty-state-icon">💬</div>
                        <p class="empty-state-text">سوالی درباره جزوات این دفتر دارید؟<br>همین‌جا بپرسید!</p>
                    </div>
                </div>

                <!-- Input -->
                <div class="chat-input-container">
                    <textarea
                        class="chat-input"
                        id="chat-input"
                        placeholder="سوال خود را بنویسید..."
                        rows="1"
                        onkeydown="handleKeyDown(event)"
                    ></textarea>
                    <button class="send-btn" id="send-btn" onclick="sendMessage()">
                        ارسال
                    </button>
                </div>
            </div>
        </main>
    </div>

    {% include 'components/mobile_nav.html' %}

    <script src="/static/js/api.js"></script>
    <script src="/static/js/common.js"></script>
    <script>
        const notebookId = {{ notebook_id }};
        let isLoading = false;

        // Initialize
        document.addEventListener('DOMContentLoaded', async () => {
            await loadChatHistory();
            await checkIndexStatus();
            setupTextareaAutoResize();
        });

        // Load chat history
        async function loadChatHistory() {
            try {
                const response = await fetch(`/api/v1/notebooks/${notebookId}/chat`);
                const data = await response.json();

                document.getElementById('notebook-title').textContent =
                    `گفتگو با: ${data.notebook_title}`;

                if (data.messages && data.messages.length > 0) {
                    document.getElementById('empty-state').style.display = 'none';
                    data.messages.forEach(msg => appendMessage(msg.role, msg.content));
                    scrollToBottom();
                }
            } catch (error) {
                console.error('Error loading chat:', error);
            }
        }

        // Check if notebook is indexed
        async function checkIndexStatus() {
            try {
                const response = await fetch(`/api/v1/notebooks/${notebookId}/chat/status`);
                const data = await response.json();

                if (!data.is_indexed) {
                    document.getElementById('not-indexed-warning').style.display = 'block';
                }
            } catch (error) {
                console.error('Error checking index:', error);
            }
        }

        // Send message
        async function sendMessage() {
            const input = document.getElementById('chat-input');
            const message = input.value.trim();

            if (!message || isLoading) return;

            isLoading = true;
            document.getElementById('send-btn').disabled = true;
            document.getElementById('empty-state').style.display = 'none';

            // Add user message
            appendMessage('user', message);
            input.value = '';
            input.style.height = 'auto';

            // Show loading
            showLoading();
            scrollToBottom();

            try {
                const response = await fetch(`/api/v1/notebooks/${notebookId}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message })
                });

                hideLoading();

                if (response.ok) {
                    const data = await response.json();
                    appendMessage('assistant', data.assistant_message.content);
                } else {
                    const error = await response.json();
                    appendMessage('assistant', `خطا: ${error.detail || 'مشکلی پیش آمد'}`);
                }
            } catch (error) {
                hideLoading();
                appendMessage('assistant', 'خطا در برقراری ارتباط با سرور');
            }

            isLoading = false;
            document.getElementById('send-btn').disabled = false;
            scrollToBottom();
        }

        // Append message to chat
        function appendMessage(role, content) {
            const container = document.getElementById('messages-container');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${role}`;

            const avatar = role === 'user' ? '👤' : '🤖';

            messageDiv.innerHTML = `
                <div class="message-avatar">${avatar}</div>
                <div class="message-content">${formatMessage(content)}</div>
            `;

            container.appendChild(messageDiv);
        }

        // Format message (convert markdown-like to HTML)
        function formatMessage(text) {
            return text
                .replace(/\n/g, '<br>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>');
        }

        // Show loading indicator
        function showLoading() {
            const container = document.getElementById('messages-container');
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'loading-indicator';
            loadingDiv.id = 'loading-indicator';
            loadingDiv.innerHTML = `
                <span>در حال فکر کردن</span>
                <div class="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            `;
            container.appendChild(loadingDiv);
        }

        // Hide loading indicator
        function hideLoading() {
            const loading = document.getElementById('loading-indicator');
            if (loading) loading.remove();
        }

        // Clear chat
        async function clearChat() {
            if (!confirm('آیا از پاک کردن گفتگو مطمئن هستید؟')) return;

            try {
                await fetch(`/api/v1/notebooks/${notebookId}/chat`, {
                    method: 'DELETE'
                });

                const container = document.getElementById('messages-container');
                container.innerHTML = `
                    <div class="empty-state" id="empty-state">
                        <div class="empty-state-icon">💬</div>
                        <p class="empty-state-text">سوالی درباره جزوات این دفتر دارید؟<br>همین‌جا بپرسید!</p>
                    </div>
                `;
            } catch (error) {
                console.error('Error clearing chat:', error);
            }
        }

        // Handle Enter key
        function handleKeyDown(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }

        // Auto-resize textarea
        function setupTextareaAutoResize() {
            const textarea = document.getElementById('chat-input');
            textarea.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 120) + 'px';
            });
        }

        // Scroll to bottom
        function scrollToBottom() {
            const container = document.getElementById('messages-container');
            container.scrollTop = container.scrollHeight;
        }
    </script>
</body>
</html>
```

### ۹.۳ اضافه کردن دکمه چت به `app/templates/notes.html`

در بخش header صفحه notes، اضافه کردن دکمه:

```html
<button class="button-primary" onclick="openNotebookChat()" style="display: flex; align-items: center; gap: 0.5rem;">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
    گفتگو با دفتر
</button>

<script>
function openNotebookChat() {
    const notebookId = new URLSearchParams(window.location.search).get('notebook_id');
    window.location.href = `/chat?notebook_id=${notebookId}`;
}
</script>
```

---

## فاز ۱۰: یکپارچه‌سازی با Workflow موجود

### ۱۰.۱ آپدیت Worker Tasks (`app/worker/tasks.py`)

بعد از پردازش موفق جزوه، ایندکس کردن:

```python
from app.services.vector_service import index_note

# در انتهای تابع process_file_with_credits، بعد از ذخیره نتیجه:
if result.get("note"):
    try:
        chunks_indexed = index_note(
            notebook_id=note.notebook_id,
            note_id=note.id,
            title=result.get("title", note.title),
            html_content=result.get("note")
        )
        print(f"[WORKER] Indexed {chunks_indexed} chunks for note {note.id}")
    except Exception as e:
        print(f"[WORKER] Warning: Failed to index note {note.id}: {e}")
        # ادامه بده حتی اگر ایندکس شکست خورد
```

### ۱۰.۲ آپدیت Note CRUD (`app/crud/note.py`)

در تابع update:
```python
from app.services.vector_service import index_note

async def update_note(...):
    # ... کد موجود ...

    # آپدیت ایندکس
    if note.user_edited_text or note.gemini_output_text:
        content = note.user_edited_text or note.gemini_output_text
        index_note(note.notebook_id, note.id, note.title, content)

    return note
```

در تابع delete:
```python
from app.services.vector_service import delete_note_from_index

async def delete_note(...):
    # حذف از ایندکس قبل از حذف از دیتابیس
    delete_note_from_index(note.notebook_id, note.id)

    # ... کد موجود حذف ...
```

### ۱۰.۳ آپدیت Notebook CRUD (`app/crud/notebook.py`)

در تابع delete:
```python
from app.services.vector_service import delete_notebook_index

async def delete_notebook(...):
    # حذف ایندکس کامل دفتر
    delete_notebook_index(notebook_id)

    # ... کد موجود حذف ...
```

---

## فاز ۱۱: تست و Debug

### ۱۱.۱ تست‌های دستی
1. ایجاد یک جزوه جدید و بررسی ایندکس شدن
2. چت با دفتر و بررسی پاسخ‌ها
3. ویرایش جزوه و بررسی آپدیت ایندکس
4. پاک کردن چت
5. حذف جزوه و بررسی حذف از ایندکس

### ۱۱.۲ نکات Debug
- لاگ‌های vector_service برای بررسی ایندکس
- لاگ‌های rag_service برای بررسی context
- بررسی ChromaDB با `chromadb_client.list_collections()`

---

## خلاصه فایل‌ها

### فایل‌های جدید (۷ عدد)
| فایل | توضیح |
|------|-------|
| `app/services/embedding_service.py` | تولید embedding و chunking |
| `app/services/vector_service.py` | مدیریت ChromaDB |
| `app/services/rag_service.py` | منطق RAG و چت با Gemini |
| `app/schemas/chat.py` | Pydantic schemas |
| `app/crud/chat.py` | عملیات دیتابیس چت |
| `app/api/v1/chat.py` | API endpoints |
| `app/templates/chat.html` | صفحه چت |

### فایل‌های موجود که تغییر می‌کنند (۸ عدد)
| فایل | تغییرات |
|------|---------|
| `requirements.txt` | اضافه کردن chromadb, sentence-transformers |
| `app/core/config.py` | تنظیمات ChromaDB |
| `app/db/models.py` | مدل‌های ChatSession, ChatMessage |
| `app/main.py` | Route چت و include router |
| `app/templates/notes.html` | دکمه گفتگو با دفتر |
| `app/worker/tasks.py` | ایندکس کردن بعد از پردازش |
| `app/crud/note.py` | آپدیت/حذف ایندکس |
| `app/crud/notebook.py` | حذف ایندکس دفتر |

---

## ترتیب پیاده‌سازی پیشنهادی

1. ✅ نصب dependencies
2. ✅ تنظیمات config
3. ✅ مدل‌های دیتابیس + migration
4. ✅ embedding_service
5. ✅ vector_service
6. ✅ rag_service
7. ✅ chat schemas + crud
8. ✅ chat API endpoints
9. ✅ صفحه chat.html
10. ✅ دکمه در notes.html
11. ✅ یکپارچه‌سازی با tasks
12. ✅ تست کامل
