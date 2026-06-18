FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y ffmpeg \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY requirements.txt /app/requirements.txt

ENV DATA_DIR=/app/data \
    DB_PATH=/app/db/app.db \
    APP_SECRET=changeme

VOLUME ["/app/data", "/app/db"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
