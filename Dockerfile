# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Copy custom NGINX config
COPY nginx/default.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Ensure Flask session works — Set a secret key (optional if handled in app config)
ENV FLASK_SECRET_KEY="your-secret-key"

# Expose HTTP port
EXPOSE 80

# Start Gunicorn and NGINX
CMD bash -c "gunicorn chessy:app --bind 127.0.0.1:8000 & nginx -g 'daemon off;'"
