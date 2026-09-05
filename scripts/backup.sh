#!/bin/bash
# Резервная копия базы и фотографий — она же архив для переезда на другой сервер.
# В cron:  0 3 * * * /путь/к/проекту/scripts/backup.sh
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; . ./.env; set +a

PROJECT="${COMPOSE_PROJECT_NAME:-pandus}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/$PROJECT}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y-%m-%d_%H%M)"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] База…"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" \
  | gzip > "$BACKUP_DIR/db_$STAMP.sql.gz"

echo "[$(date)] Фотографии…"
docker run --rm \
  -v "${PROJECT}_photos:/data:ro" \
  -v "$BACKUP_DIR:/backup" \
  alpine tar czf "/backup/photos_$STAMP.tar.gz" -C /data .

echo "[$(date)] Чищу копии старше $KEEP_DAYS дней…"
find "$BACKUP_DIR" -name '*.gz' -mtime +"$KEEP_DAYS" -delete

echo "[$(date)] Готово:"
ls -lh "$BACKUP_DIR" | tail -5

# Копии на том же сервере не спасают от его потери.
# Настройте выгрузку BACKUP_DIR наружу: rclone, scp на другой хост
# или объектное хранилище.
