# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Add metadata labels for GitHub Container Registry
LABEL org.opencontainers.image.title="ACST-DL"
LABEL org.opencontainers.image.description="A Podcast MP3 Downloader with modern web interface for downloading MP3 files from podcast feeds"
LABEL org.opencontainers.image.url="https://github.com/OWNER/REPO"
LABEL org.opencontainers.image.source="https://github.com/OWNER/REPO"
LABEL org.opencontainers.image.version="3.1.0"
LABEL org.opencontainers.image.vendor="ACST-DL"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.documentation="https://github.com/OWNER/REPO#readme"

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --only=main --no-root \
    && rm -rf $POETRY_CACHE_DIR

# Copy application code
COPY . .

# Create podcasts directory with proper permissions
RUN mkdir -p /app/podcasts && chmod 755 /app/podcasts

# Create non-root user for security
RUN adduser --disabled-password --gecos '' --uid 1000 appuser \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Default command to run the web application
CMD ["python", "web_app.py"]
