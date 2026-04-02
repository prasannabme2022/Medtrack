# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy project
COPY . /app/

# Create uploads directory
RUN mkdir -p medtrack/uploads

# Expose port
EXPOSE 8000

# Run gunicorn
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:8000", "app:app"]
