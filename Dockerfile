# Use Python 3.9 slim image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create a non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Create directory for credentials
RUN mkdir -p /app/credentials

# Copy credentials file (will be mounted at runtime)
VOLUME ["/app/credentials"]

# Expose port
EXPOSE 8000

# Run the application
CMD ["gunicorn", "weats_backend.wsgi:application", "--bind", "0.0.0.0:8000"] 