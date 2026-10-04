FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/srv
WORKDIR /srv
# Tesseract is the OCR engine for scanned PDFs and images.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
# --proxy-headers lets rate limiting see the real client IP when running behind a proxy/load balancer.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
