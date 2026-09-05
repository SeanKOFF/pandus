FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# libpq — для psycopg, остальное нужно Pillow для JPEG
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Запуск не от root: если кто-то пробьётся через приложение,
# он не получит прав на систему внутри контейнера
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/staticfiles /data/photos \
    && chown -R app:app /app /data
USER app

EXPOSE 8000
