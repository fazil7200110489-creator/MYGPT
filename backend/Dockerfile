FROM python:3.12-slim

WORKDIR /app

# System dependencies for PyMuPDF / Tesseract OCR fallback / llama-cpp-python build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    tesseract-ocr \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-tender.txt .
RUN pip install --no-cache-dir -r requirements-tender.txt

COPY backend ./backend
COPY pytest.ini .

# Persistent runtime volumes (models and job state are mounted at runtime, not baked into image)
VOLUME ["/app/models", "/app/data", "/app/logs"]

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

