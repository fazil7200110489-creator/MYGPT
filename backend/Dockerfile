
FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    tesseract-ocr \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements-tender.txt ./requirements-tender.txt

RUN pip install --no-cache-dir -r requirements-tender.txt

# Copy backend source
COPY backend/ ./backend/

# Copy test configuration
COPY pytest.ini ./pytest.ini

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
