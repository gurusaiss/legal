FROM python:3.12-slim

# tesseract-ocr: the OCR engine itself (pytesseract is just a wrapper around this binary).
# libgl1/libglib2.0-0: runtime libs opencv-python-headless needs even in "headless" mode.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY rules ./rules

# Persisted at runtime via the compose volume — created here so a bind mount isn't required to boot.
RUN mkdir -p uploads reports

EXPOSE 8000

# Most PaaS hosts (Railway, Render, etc.) inject $PORT and route traffic to
# whatever it's set to — shell form so that variable actually expands;
# falls back to 8000 for plain `docker run` / docker-compose where it's unset.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
