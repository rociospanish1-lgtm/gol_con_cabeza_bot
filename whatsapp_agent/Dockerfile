FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Los datos (estado on/off, historial) viven en /app/data: monta ahí un volumen para no perderlos.
VOLUME ["/app/data"]
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
