# C:\excel-to-web\Dockerfile

FROM python:3.11-slim as builder
WORKDIR /app
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache /wheels/*
COPY . .

# Uvicorn будет слушать порт 10000. Fly.io сам пробросит к нему внешний 80/443 порт.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]