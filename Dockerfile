# Use latest Alpine Linux image as base
FROM alpine:latest

# Add metadata labels for GitHub Container Registry
LABEL org.opencontainers.image.title="ACST-DL"
LABEL org.opencontainers.image.description="A Podcast MP3 Downloader with modern web interface for downloading MP3 files from podcast feeds"
LABEL org.opencontainers.image.url="https://github.com/OWNER/REPO"
LABEL org.opencontainers.image.source="https://github.com/OWNER/REPO"
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
RUN apk add --no-cache \
    python3 \
    py3-pip \
    curl \
    shadow

# Install Poetry
RUN pip install --break-system-packages poetry

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && PIP_BREAK_SYSTEM_PACKAGES=1 poetry install --only=main --no-root \
    && rm -rf $POETRY_CACHE_DIR

# Copy application code
COPY . .

# Create podcasts directory with proper permissions
RUN mkdir -p /app/podcasts && chmod 755 /app/podcasts

# Create non-root user for security
RUN adduser -D -u 1000 appuser \
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
