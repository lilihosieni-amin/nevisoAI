"""
Comprehensive error handling for Celery worker tasks
"""
from enum import Enum
from typing import Dict, Tuple
import traceback


class ErrorCategory(str, Enum):
    """Categories of errors that can occur during processing"""
    NETWORK_ERROR = "network_error"  # Connection issues with Gemini
    API_ERROR = "api_error"  # Gemini API errors (quota, auth, etc.)
    FILE_ERROR = "file_error"  # File reading/format issues
    PARSING_ERROR = "parsing_error"  # JSON parsing errors
    DATABASE_ERROR = "database_error"  # Database connection/query errors
    UNKNOWN_ERROR = "unknown_error"  # Unexpected errors


class ProcessingError:
    """
    Classify and format errors for user-friendly messages
    """

    # Error patterns and their user-friendly messages (Persian)
    ERROR_PATTERNS = {
        # Gemini API Errors
        "quota": {
            "category": ErrorCategory.API_ERROR,
            "user_message": "سهمیه استفاده از هوش مصنوعی تمام شده است. لطفاً بعداً دوباره تلاش کنید.",
            "retryable": False
        },
        "rate limit": {
            "category": ErrorCategory.API_ERROR,
            "user_message": "تعداد درخواست‌ها بیش از حد مجاز است. لطفاً کمی صبر کنید و دوباره تلاش کنید.",
            "retryable": True
        },
        "authentication": {
            "category": ErrorCategory.API_ERROR,
            "user_message": "خطا در احراز هویت با سرویس هوش مصنوعی. لطفاً با پشتیبانی تماس بگیرید.",
            "retryable": False
        },
        "403": {
            "category": ErrorCategory.API_ERROR,
            "user_message": "دسترسی به سرویس هوش مصنوعی مسدود شده است. لطفاً با پشتیبانی تماس بگیرید.",
            "retryable": False
        },
        "invalid file": {
            "category": ErrorCategory.FILE_ERROR,
            "user_message": "فایل آپلود شده قابل پردازش نیست. لطفاً فرمت فایل را بررسی کنید.",
            "retryable": False
        },
        "file not found": {
            "category": ErrorCategory.FILE_ERROR,
            "user_message": "فایل آپلود شده یافت نشد. لطفاً دوباره آپلود کنید.",
            "retryable": False
        },
        "unsupported format": {
            "category": ErrorCategory.FILE_ERROR,
            "user_message": "فرمت فایل پشتیبانی نمی‌شود. فقط فایل‌های صوتی و تصویری مجاز هستند.",
            "retryable": False
        },
        "timeout": {
            "category": ErrorCategory.NETWORK_ERROR,
            "user_message": "زمان پردازش به پایان رسید. لطفاً دوباره تلاش کنید.",
            "retryable": True
        },
        "connection": {
            "category": ErrorCategory.NETWORK_ERROR,
            "user_message": "خطا در برقراری ارتباط با سرویس. لطفاً دوباره تلاش کنید.",
            "retryable": True
        },
        "network": {
            "category": ErrorCategory.NETWORK_ERROR,
            "user_message": "خطای شبکه. لطفاً اتصال اینترنت خود را بررسی کنید.",
            "retryable": True
        },
        "json": {
            "category": ErrorCategory.PARSING_ERROR,
            "user_message": "خطا در تفسیر خروجی هوش مصنوعی. در حال تلاش مجدد...",
            "retryable": True
        },
        "database": {
            "category": ErrorCategory.DATABASE_ERROR,
            "user_message": "خطا در ذخیره‌سازی اطلاعات. لطفاً دوباره تلاش کنید.",
            "retryable": True
        },
        "models/gemini": {
            "category": ErrorCategory.API_ERROR,
            "user_message": "مدل هوش مصنوعی در دسترس نیست. لطفاً با پشتیبانی تماس بگیرید.",
            "retryable": False
        }
    }

    @classmethod
    def classify_error(cls, error: Exception) -> Tuple[ErrorCategory, str, str, bool]:
        """
        Classify an error and return category, user message, and technical details

        Returns:
            Tuple of (category, user_message, error_detail, is_retryable)
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Get full traceback for technical details
        error_detail = f"{error_type}: {str(error)}\n\n{traceback.format_exc()}"

        # Try to match error patterns
        for pattern, info in cls.ERROR_PATTERNS.items():
            if pattern in error_str:
                return (
                    info["category"],
                    info["user_message"],
                    error_detail,
                    info["retryable"]
                )

        # Default for unknown errors
        return (
            ErrorCategory.UNKNOWN_ERROR,
            f"خطای غیرمنتظره در پردازش فایل: {error_type}. لطفاً با پشتیبانی تماس بگیرید.",
            error_detail,
            False  # Don't retry unknown errors by default
        )

    @classmethod
    def should_retry(cls, error: Exception, current_retry_count: int, max_retries: int = 3) -> bool:
        """
        Determine if we should retry processing after this error

        Args:
            error: The exception that occurred
            current_retry_count: Number of times already retried
            max_retries: Maximum number of retry attempts

        Returns:
            True if should retry, False otherwise
        """
        if current_retry_count >= max_retries:
            return False

        category, _, _, retryable = cls.classify_error(error)
        return retryable

    @classmethod
    def get_retry_delay(cls, retry_count: int) -> int:
        """
        Get delay in seconds before retry (exponential backoff)

        Args:
            retry_count: Current retry attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: 5s, 15s, 45s
        return 5 * (3 ** retry_count)
