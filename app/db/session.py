from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Create async engine (for FastAPI endpoints)
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create sync engine (for Celery workers)
# Convert async URLs to sync pymysql URL
sync_database_url = settings.DATABASE_URL
if "asyncmy" in sync_database_url:
    sync_database_url = sync_database_url.replace("mysql+asyncmy://", "mysql+pymysql://")
    sync_database_url = sync_database_url.replace("asyncmy+asyncio://", "mysql+pymysql://")

print(f"[DB] Async URL: {settings.DATABASE_URL}")
print(f"[DB] Sync URL: {sync_database_url}")

sync_engine = create_engine(
    sync_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600  # Recycle connections after 1 hour
)

# Create async session factory (for FastAPI)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Create sync session factory (for Celery)
SyncSessionLocal = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncSession:
    """Dependency for getting async database sessions (for FastAPI endpoints)"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_db() -> Session:
    """Get sync database session (for Celery workers)"""
    session = SyncSessionLocal()
    try:
        return session
    except Exception:
        session.close()
        raise
