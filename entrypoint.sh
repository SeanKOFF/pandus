#!/bin/sh
# Ждём базу, применяем миграции, собираем статику — затем передаём
# управление команде из docker-compose (gunicorn или бот).
set -e

echo "Ожидание PostgreSQL…"
until python -c "
import os, socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect((os.environ.get('DB_HOST','db'), int(os.environ.get('DB_PORT','5432'))))
except OSError:
    sys.exit(1)
" 2>/dev/null; do
  sleep 1
done

if [ "$1" = "gunicorn" ]; then
  echo "Применяем миграции…"
  python manage.py migrate --noinput
  echo "Компилируем переводы…"
  python manage.py compilemessages 2>/dev/null || true
  echo "Собираем статику…"
  python manage.py collectstatic --noinput
fi

exec "$@"
