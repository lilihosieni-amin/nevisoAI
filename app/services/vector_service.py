"""
سرویس مدیریت Vector Database با ChromaDB
"""
import chromadb
from chromadb.config import Settings
from typing import List, Optional
from app.core.config import settings
from app.services.embedding_service import generate_embedding, generate_embeddings, prepare_note_for_indexing

# Initialize ChromaDB client (lazy loading)
_client = None


def get_chroma_client() -> chromadb.Client:
    """Get or create ChromaDB client"""
    global _client
    if _client is None:
        print(f"[VECTOR] Initializing ChromaDB at: {settings.CHROMA_PERSIST_DIRECTORY}")
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIRECTORY,
            settings=Settings(anonymized_telemetry=False)
        )
        print("[VECTOR] ChromaDB initialized successfully")
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
    print(f"[VECTOR] Indexing note {note_id} for notebook {notebook_id}")

    # اول chunks قبلی این جزوه رو حذف کن
    delete_note_from_index(notebook_id, note_id)

    # آماده‌سازی documents
    documents = prepare_note_for_indexing(note_id, title, html_content)

    if not documents:
        print(f"[VECTOR] No content to index for note {note_id}")
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

    print(f"[VECTOR] Indexed {len(documents)} chunks for note {note_id}")
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
            print(f"[VECTOR] Deleted {len(results['ids'])} chunks for note {note_id}")

        return True
    except Exception as e:
        print(f"[VECTOR] Error deleting note {note_id} from index: {e}")
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
        collection_names = [c.name for c in collections]

        if collection_name in collection_names:
            client.delete_collection(collection_name)
            print(f"[VECTOR] Deleted collection for notebook {notebook_id}")

        return True
    except Exception as e:
        print(f"[VECTOR] Error deleting notebook {notebook_id} index: {e}")
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

    try:
        collection = get_notebook_collection(notebook_id)

        # بررسی خالی بودن collection
        if collection.count() == 0:
            print(f"[VECTOR] Collection for notebook {notebook_id} is empty")
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

        print(f"[VECTOR] Found {len(formatted_results)} relevant chunks for query")
        return formatted_results

    except Exception as e:
        print(f"[VECTOR] Error searching in notebook {notebook_id}: {e}")
        return []


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
    except Exception as e:
        print(f"[VECTOR] Error getting stats for notebook {notebook_id}: {e}")
        return {"total_chunks": 0, "collection_name": None}


def reindex_notebook(notebook_id: int, notes: List[dict]) -> int:
    """
    ایندکس مجدد کل دفتر

    Args:
        notebook_id: شناسه دفتر
        notes: لیست جزوات با id, title, content

    Returns:
        تعداد کل chunks ایندکس شده
    """
    # حذف ایندکس قبلی
    delete_notebook_index(notebook_id)

    total_chunks = 0
    for note in notes:
        chunks = index_note(
            notebook_id=notebook_id,
            note_id=note["id"],
            title=note["title"],
            html_content=note["content"]
        )
        total_chunks += chunks

    print(f"[VECTOR] Reindexed notebook {notebook_id}: {total_chunks} total chunks")
    return total_chunks
