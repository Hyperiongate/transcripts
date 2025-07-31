# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy language model separately to avoid timeout
RUN pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p static/css static/js templates services

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Render uses PORT environment variable
EXPOSE ${PORT}

# Run the application with Render's PORT
CMD gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 app:app
