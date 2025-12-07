"""
Custom exceptions for AI processing errors
"""


class AIProcessingError(Exception):
    """Base exception for AI processing errors"""
    def __init__(self, message: str, error_type: str):
        self.message = message
        self.error_type = error_type
        super().__init__(self.message)


class QuotaExceededError(AIProcessingError):
    """Raised when Gemini API quota is exceeded"""
    def __init__(self, message: str = "اعتبار API شما تمام شده است"):
        super().__init__(message, "quota_exceeded")


class InvalidFormatError(AIProcessingError):
    """Raised when file format is invalid or unsupported"""
    def __init__(self, message: str = "فرمت فایل نامعتبر است"):
        super().__init__(message, "invalid_format")


class NetworkError(AIProcessingError):
    """Raised when network connection fails"""
    def __init__(self, message: str = "خطا در اتصال به سرویس. لطفا اتصال اینترنت خود را بررسی کنید"):
        super().__init__(message, "network_error")


class ProcessingTimeoutError(AIProcessingError):
    """Raised when processing takes too long"""
    def __init__(self, message: str = "زمان پردازش فایل تمام شد. لطفا دوباره تلاش کنید"):
        super().__init__(message, "processing_timeout")


class FileTooLargeError(AIProcessingError):
    """Raised when file size is too large"""
    def __init__(self, message: str = "حجم فایل بیش از حد مجاز است"):
        super().__init__(message, "file_too_large")


class ContentGenerationError(AIProcessingError):
    """Raised when Gemini fails to generate content"""
    def __init__(self, message: str = "خطا در تولید محتوا. لطفا دوباره تلاش کنید"):
        super().__init__(message, "content_generation_error")


class UnknownAIError(AIProcessingError):
    """Raised for unknown AI processing errors"""
    def __init__(self, message: str = "خطای ناشناخته در پردازش فایل"):
        super().__init__(message, "unknown_error")
