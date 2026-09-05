#!/bin/bash
# Восстановление из резервной копии. Он же — второй шаг переезда:
# те же архивы, что делает backup.sh, разворачиваются на новом сервере.
#
# Использование:
#   ./scripts/restore.sh /путь/db_2026-09-05_0300.sql.gz /путь/photos_2026-09-05_0300.tar.gz
set -euo pipefail

DB_DUMP="${1:?Укажите файл дампа базы (db_*.sql.gz)}"
PHOTOS_ARCHIVE="${2:-}"

cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; . ./.env; set +a
PROJECT="${COMPOSE_PROJECT_NAME:-pandus}"

echo "ВНИМАНИЕ: текущее содержимое базы «$DB_NAME» будет заменено."
read -r -p "Продолжить? [y/N] " ans
[ "$ans" = "y" ] || { echo "Отменено"; exit 1; }

echo "Поднимаю базу…"
docker compose up -d db
until docker compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
  sleep 1
done

echo "Останавливаю приложение, чтобы никто не писал во время восстановления…"
docker compose stop web bot 2>/dev/null || true

echo "Восстанавливаю базу…"
docker compose exec -T db psql -U "$DB_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";"
gunzip -c "$DB_DUMP" | docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME"

if [ -n "$PHOTOS_ARCHIVE" ]; then
  echo "Восстанавливаю фотографии…"
  docker volume create "${PROJECT}_photos" >/dev/null
  docker run --rm \
    -v "${PROJECT}_photos:/data" \
    -v "$(cd "$(dirname "$PHOTOS_ARCHIVE")" && pwd):/backup:ro" \
    alpine sh -c "rm -rf /data/* && tar xzf /backup/$(basename "$PHOTOS_ARCHIVE") -C /data"
else
  echo "Архив фотографий не указан — пропускаю."
fi

echo "Запускаю приложение…"
docker compose up -d

echo "Готово. Проверьте: docker compose ps && docker compose logs -f"
