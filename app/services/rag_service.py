"""
سرویس RAG برای چت با دفتر
"""
# Import and configure Gemini FIRST before any other imports
from app.services.gemini_config import configure_gemini
configure_gemini()

import google.generativeai as genai
from typing import List, Optional
from app.core.config import settings
from app.services.vector_service import search as vector_search

# System instruction برای چت
CHAT_SYSTEM_INSTRUCTION = """
شما «نویسو»، یک دستیار هوشمند و متخصص برای کمک به دانشجویان هستید.
وظیفه شما پاسخگویی به سوالات کاربر با اولویت‌بندی دقیق منابع اطلاعاتی است.

### محتوای مرتبط از جزوات درسی (Context):
{context}

### دستورالعمل‌های پاسخگویی (بسیار مهم):
شما باید همیشه به سوال کاربر پاسخ دهید، اما نحوه پاسخگویی شما بستگی به وجود اطلاعات در «محتوای مرتبط» دارد:

1. **حالت اول: اگر پاسخ در «محتوای مرتبط» موجود است:**
   - پاسخ را با عبارت: "طبق محتوای جزوه، ..." یا "بر اساس جزوه درسی، ..." شروع کنید.
   - پاسخ را دقیقاً از متن استخراج کنید و به آن وفادار باشید.

2. **حالت دوم: اگر پاسخ در «محتوای مرتبط» یافت نشد:**
   - ابتدا صریحاً ذکر کنید: "این مورد در جزوه ذکر نشده است، اما پاسخ صحیح این است که: ..."
   - سپس پاسخ کامل و صحیح را با استفاده از دانش عمومی خود ارائه دهید.

### قوانین کلی:
- لحن شما باید آموزشی، محترمانه و دقیق باشد.
- پاسخ‌ها را ساختاریافته (با استفاده از بولت پوینت یا شماره‌گذاری) ارائه دهید تا خوانایی بالا برود.
- از توضیحات حاشیه‌ای و طولانی پرهیز کنید؛ پاسخ باید مختصر و مفید باشد.
- زبان پاسخ باید دقیقاً همان زبان سوال کاربر باشد (فارسی یا انگلیسی).

الان به سوال زیر با توجه به دستورالعمل‌های بالا پاسخ بده:
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
    print(f"[RAG] Processing query for notebook {notebook_id}: {user_query[:100]}...")

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
        print(f"[RAG] Found {len(relevant_chunks)} relevant chunks")
        print(f"[RAG] Context content:\n{'='*50}\n{context}\n{'='*50}")
    else:
        context = "هیچ محتوای مرتبطی یافت نشد. لطفاً به کاربر بگویید که جزوات این دفتر هنوز ایندکس نشده‌اند یا محتوای مرتبطی وجود ندارد."
        print("[RAG] No relevant chunks found")

    # ۳. ساخت system instruction با context
    system_instruction = CHAT_SYSTEM_INSTRUCTION.format(context=context)

    # ۴. Reconfigure Gemini (needed after embedding service runs)
    configure_gemini()

    # ۵. ایجاد مدل
    model = genai.GenerativeModel(
        model_name=settings.GEMINI_CHAT_MODEL,
        system_instruction=system_instruction
    )

    # ۵. شروع چت با history
    chat = model.start_chat(history=chat_history or [])

    # ۶. ارسال پیام و دریافت پاسخ
    try:
        response = chat.send_message(user_query)
        print(f"[RAG] Response generated: {len(response.text)} chars")
        return response.text
    except Exception as e:
        print(f"[RAG] Error in chat: {e}")
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


def format_chat_history_for_gemini(messages: list) -> List[dict]:
    """
    تبدیل پیام‌های دیتابیس به فرمت Gemini chat history

    Args:
        messages: لیست پیام‌ها از دیتابیس

    Returns:
        فرمت history برای Gemini
    """
    history = []
    for msg in messages:
        history.append({
            "role": msg.role if hasattr(msg, 'role') else msg.get('role'),
            "parts": [msg.content if hasattr(msg, 'content') else msg.get('content')]
        })
    return history
