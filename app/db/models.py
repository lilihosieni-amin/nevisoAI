from sqlalchemy import Column, Integer, String, TIMESTAMP, Boolean, Enum, DECIMAL, BigInteger, Date, JSON, ForeignKey, Text, SMALLINT
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(20), nullable=False, unique=True, index=True)
    email = Column(String(255), unique=True, nullable=True)
    full_name = Column(String(100), nullable=True)
    university = Column(String(100), nullable=True)
    field_of_study = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    otps = relationship("UserOTP", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("UserSubscription", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    notebooks = relationship("Notebook", back_populates="user", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="user", cascade="all, delete-orphan")
    uploads = relationship("Upload", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")


class UserOTP(Base):
    __tablename__ = "user_otps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    otp_code = Column(String(6), nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    user = relationship("User", back_populates="otps")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(SMALLINT, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    price_toman = Column(DECIMAL(10, 0), nullable=False)
    duration_days = Column(Integer, nullable=False)
    max_minutes = Column(Integer, nullable=False)
    max_notebooks = Column(Integer, nullable=False)
    features = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    subscriptions = relationship("UserSubscription", back_populates="plan")


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    cancelled = "cancelled"


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(SMALLINT, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    start_date = Column(TIMESTAMP, nullable=False)
    end_date = Column(TIMESTAMP, nullable=False)
    minutes_consumed = Column(Integer, default=0, nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.active, nullable=False)

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription", cascade="all, delete-orphan")


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.id", ondelete="CASCADE"), nullable=False)
    amount_toman = Column(DECIMAL(10, 0), nullable=False)
    payment_gateway = Column(String(50), nullable=False)
    transaction_ref_id = Column(String(255), unique=True, nullable=False)
    status = Column(Enum(PaymentStatus), nullable=False)
    paid_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    user = relationship("User", back_populates="payments")
    subscription = relationship("UserSubscription", back_populates="payments")


class Notebook(Base):
    __tablename__ = "notebooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(100), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    user = relationship("User", back_populates="notebooks")
    notes = relationship("Note", back_populates="notebook", cascade="all, delete-orphan")
    chat_session = relationship("ChatSession", back_populates="notebook", uselist=False, cascade="all, delete-orphan")


class NoteStatus(str, enum.Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    session_date = Column(String(10), nullable=True)  # Jalali date format: YYYY/MM/DD
    gemini_output_text = Column(Text, nullable=True)  # LONGTEXT: HTML note from Gemini
    user_edited_text = Column(Text, nullable=True)    # LONGTEXT: HTML note edited by user
    status = Column(Enum(NoteStatus), default=NoteStatus.processing, nullable=False)

    # Error handling fields
    error_type = Column(String(50), nullable=True)  # Error type (quota_exceeded, invalid_format, etc.)
    error_message = Column(String(500), nullable=True)  # User-friendly error message
    error_detail = Column(Text, nullable=True)  # Technical error details for debugging
    retry_count = Column(SMALLINT, default=0, nullable=False)  # Number of retry attempts
    last_error_at = Column(TIMESTAMP, nullable=True)  # When the last error occurred

    # Soft delete field
    is_active = Column(Boolean, default=True, nullable=False)  # Soft delete flag

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    notebook = relationship("Notebook", back_populates="notes")
    user = relationship("User", back_populates="notes")
    uploads = relationship("Upload", back_populates="note", cascade="all, delete-orphan")


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_file_name = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    note = relationship("Note", back_populates="uploads")
    user = relationship("User", back_populates="uploads")


class NotificationType(str, enum.Enum):
    note_completed = "note_completed"
    note_failed = "note_failed"
    subscription_expiring = "subscription_expiring"
    quota_warning = "quota_warning"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(100), nullable=False)
    message = Column(String(500), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    related_note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    user = relationship("User", back_populates="notifications")
    note = relationship("Note")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action_type = Column(String(50), nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    user = relationship("User", back_populates="activity_logs")


class TransactionType(str, enum.Enum):
    deduct = "deduct"
    refund = "refund"
    purchase = "purchase"
    bonus = "bonus"


class CreditTransaction(Base):
    """لاگ تمام تراکنش‌های اعتبار"""
    __tablename__ = "credit_transactions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.id", ondelete="SET NULL"), nullable=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="SET NULL"), nullable=True)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)  # دقیقه
    balance_before = Column(DECIMAL(10, 2), nullable=False)
    balance_after = Column(DECIMAL(10, 2), nullable=False)
    description = Column(String(500), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    user = relationship("User")
    subscription = relationship("UserSubscription")
    note = relationship("Note")


class QueueStatus(str, enum.Enum):
    waiting = "waiting"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ProcessingQueue(Base):
    """وضعیت صف پردازش"""
    __tablename__ = "processing_queue"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    priority = Column(SMALLINT, default=0, nullable=False)  # 0=normal, 1=premium, 2=urgent
    status = Column(Enum(QueueStatus), default=QueueStatus.waiting, nullable=False)
    retry_count = Column(SMALLINT, default=0, nullable=False)
    estimated_credits = Column(DECIMAL(10, 2), nullable=True)  # تخمین اعتبار مورد نیاز
    added_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    note = relationship("Note")
    user = relationship("User")


class UserQuota(Base):
    """محدودیت‌های کاربر"""
    __tablename__ = "user_quotas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    daily_upload_count = Column(Integer, default=0, nullable=False)
    last_upload_at = Column(TIMESTAMP, nullable=True)
    concurrent_processing = Column(SMALLINT, default=0, nullable=False)
    total_minutes_used_today = Column(DECIMAL(10, 2), default=0, nullable=False)
    last_reset_at = Column(Date, server_default=func.current_date())

    # Relationships
    user = relationship("User")


class ChatSession(Base):
    """جلسه چت برای هر دفتر - هر دفتر فقط یک session فعال دارد"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    notebook = relationship("Notebook", back_populates="chat_session")
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    """پیام‌های چت"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
