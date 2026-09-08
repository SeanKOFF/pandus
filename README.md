# Qulay shahar — карта городской доступности

Краудсорсинговая карта мест без условий для пешеходов с ограниченной
мобильностью: нет пандусов, разбитые тротуары, перекрытые проезды.
Люди отправляют геолокацию и фото проблемного места через Telegram-бота,
после модерации точка появляется на публичной карте.

Контекст проекта и принятые решения — `CLAUDE.md`.

## Как это работает

1. Пользователь пишет боту в Telegram, отправляет геолокацию и фото места.
2. Заявка попадает в очередь модерации (админ-панель).
3. Модератор проверяет фото (в т.ч. на приватность — лица, номера машин)
   и либо публикует точку, либо отклоняет.
4. Опубликованная точка видна всем на карте (Leaflet + OpenStreetMap)
   и живёт там, пока кто-то не отметит её устранённой.
5. Устранённые проблемы попадают в отчёт — это то, что можно показывать
   городским службам.

## Статус проекта

Стадия проектирования. Собраны:
- [x] Схема БД (категории, заявки, история статусов)
- [x] Backend на Django + публичный API (`/api/points/`, `/api/categories/`)
- [x] Админ-панель модерации с превью фото и действиями по статусам
- [x] Telegram-бот приёма заявок
- [x] Карта на Leaflet/OSM, читающая точки из API
- [x] Локальное хранилище фото + прокси `/media/<id>/`
- [ ] Хранилище OneDrive (интерфейс готов, backend — заглушка)
- [x] Уведомление автора заявки о публикации / устранении
- [x] Конфигурация развёртывания (Docker Compose + Caddy) — `docs/deployment.md`
- [x] Развёрнуто на боевом сервере — https://qulayshahar.uz

Подробности решений — в `docs/architecture.md`.

## Стек

- **БД:** PostgreSQL 16
- **Backend:** Django 6 — сайт, админка модерации и бот запускаются
  из одного проекта; gunicorn, Docker Compose
- **Бот:** aiogram 3, отдельным контейнером из того же образа
- **Карта:** Leaflet.js + тайлы OpenStreetMap
- **Хранилище фото:** локальный том, отдаётся через собственный
  backend-прокси `/media/<id>/`, а не прямой ссылкой. `OneDriveStorage`
  реализован интерфейсом, но остаётся заглушкой

## Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # впишите TELEGRAM_BOT_TOKEN

USE_SQLITE=1 python manage.py migrate
USE_SQLITE=1 python manage.py createsuperuser
USE_SQLITE=1 python manage.py runserver
```

В отдельной вкладке терминала — бот:

```bash
source .venv/bin/activate
USE_SQLITE=1 python manage.py bot
```

`USE_SQLITE=1` позволяет работать без поднятого PostgreSQL. Для боевого
режима уберите переменную и заполните `DB_*` в `.env`.

| Адрес | Что это |
|---|---|
| http://127.0.0.1:8000/ | Публичная карта |
| http://127.0.0.1:8000/admin/ | Админка модерации |
| http://127.0.0.1:8000/api/points/ | Точки для карты (JSON) |
| http://127.0.0.1:8000/api/categories/ | Категории для легенды |

## Развёртывание

Режим задаётся переменной `COMPOSE_FILE` в `.env`, команды в обоих
случаях одинаковые — `docker compose up -d --build`:

- `docker-compose.yml:docker-compose.shared-nginx.yml` — за уже
  работающим на сервере nginx, портов наружу не публикует
- `docker-compose.yml:docker-compose.caddy.yml` — автономно, свой Caddy
  получает TLS автоматически

Документация:

- `docs/deployment.md` — автономный сервер с нуля
- `docs/deployment-sveton.md` — рядом с работающими сайтами
- `docs/migration.md` — переезд на другой сервер или хостинг
- `docs/security-checklist.md` — чек-лист перед запуском

## Структура

```
config/          настройки и корневые URL
reports/
  models.py      Category, Reporter, Report, ReportStatusHistory
  admin.py       админка модерации
  views.py       публичный API, прокси фото, страница карты
  storage.py     абстракция хранилища (local / onedrive)
  templates/     карта на Leaflet
  management/commands/bot.py   Telegram-бот
db/schema.sql    исходная SQL-схема (справочно, источник истины — модели)
```
