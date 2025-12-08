# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU-only first (to avoid large CUDA dependencies)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies for WeasyPrint, ffmpeg and other libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-noto \
    fonts-noto-cjk \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy wheels from builder stage
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Install PyTorch CPU-only first (to avoid large CUDA dependencies)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install Python packages
RUN pip install --no-cache /wheels/*

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads chroma_db

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
