# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p uploads exports data static/css static/js templates services

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Expose port (Render will set PORT environment variable)
EXPOSE ${PORT:-10000}

# Run the application
CMD gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 120 app:app
