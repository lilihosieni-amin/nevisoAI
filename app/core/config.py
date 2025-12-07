from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Gemini AI - Direct API
    GEMINI_API_KEY: str  # Real Google API key from .env
    GEMINI_TRANSCRIPTION_MODEL: str = "gemini-2.5-flash"  # Model for note generation
    GEMINI_CHAT_MODEL: str = "gemini-2.5-flash"  # Model for RAG chat

    # Redis & Celery
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Application
    APP_NAME: str = "Neviso"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 104857600  # 100MB

    # SMS
    SMS_API_KEY: str = "mock-sms-api-key"

    # Email (for OTP)
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "lilihosieni2003@gmail.com"
    SMTP_PASSWORD: str = "xlis gfpq vcfp yrhm"

    # ZarinPal Payment Gateway
    ZARINPAL_MERCHANT_ID: str
    ZARINPAL_CALLBACK_URL: str
    ZARINPAL_SANDBOX: bool = False  # Set to True for testing

    # Queue & Rate Limiting
    MAX_CONCURRENT_PROCESSING: int = 10
    MAX_USER_UPLOADS_PER_MINUTE: int = 3
    MAX_USER_UPLOADS_PER_DAY: int = 50
    QUEUE_PROCESSOR_INTERVAL: int = 10  # seconds

    # Credit Calculation
    IMAGE_CREDIT_COST: float = 0.5  # minutes per image
    MAX_RETRY_ATTEMPTS: int = 3

    # RAG Chat Settings
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    RAG_TOP_K: int = 5  # Number of relevant chunks to retrieve
    RAG_CHUNK_SIZE: int = 500  # Characters per chunk
    RAG_CHUNK_OVERLAP: int = 50  # Overlap between chunks

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
