FROM python:3.12-slim
# Tesseract (OCR) and Poppler (PDF rasterising) are system packages
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput
CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8000}"]
