"""
سرویس تولید Embedding برای متون فارسی/انگلیسی
"""
from sentence_transformers import SentenceTransformer
from typing import List
import re
from bs4 import BeautifulSoup
from app.core.config import settings

# Load model once at startup (lazy loading)
_model = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy load embedding model"""
    global _model
    if _model is None:
        print(f"[EMBEDDING] Loading model: {settings.EMBEDDING_MODEL}")
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        print("[EMBEDDING] Model loaded successfully")
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
    if not texts:
        return []

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

    if not clean_text:
        return []

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
