# Развёртывание рядом с svetanet.uz

На сервере уже работают три сайта (svetanet.uz, chiroqyoq.uz, gazyoq.uz)
за nginx в контейнере `sveton-frontend-1`. Порты 80/443 заняты им.

Схема: наш стек не публикует портов вообще. Контейнер `pandus-web`
подключается к существующей сети `sveton_default`, и nginx проксирует
на него запросы для нового домена. База, бот и тома остаются нашими.

## Что изолировано

| Ресурс | Как разделено |
|---|---|
| База | Свой PostgreSQL `pandus-db`, к базам sveton и kurbanoff доступа нет |
| Сеть | `db` и `bot` только во внутренней сети; наружу смотрит один `web` |
| Файлы | Отдельные тома `pandus_pgdata`, `pandus_photos` |
| Код | Отдельная папка, отдельный git-репозиторий |
| Удаление | `docker compose down -v` убирает всё, соседей не трогает |

Единственная точка соприкосновения — один новый файл в конфигурации
nginx. Существующий `default.conf` не изменяется.

## Главный риск и как он снят

Если в конфиге написать `proxy_pass http://pandus-web:8000` напрямую,
nginx при старте попытается разрешить это имя. Когда наш контейнер
недоступен, nginx **не стартует вообще** — и вместе с картой лягут все
три работающих сайта.

Поэтому используется `resolver 127.0.0.11` с проксированием через
переменную — тот же приём, что уже применён для upstream `api`. При
недоступном контейнере посетитель карты получит 502, а соседние сайты
продолжат работать.

## 1. DNS

Добавьте A-запись `qulayshahar.uz` на IP сервера. Проверка:

```bash
dig qulayshahar.uz +short
```

Пока запись не разошлась, сертификат не выпустится.

## 2. Сертификат

Порт 80 занят контейнером, поэтому `--standalone` потребует его остановки.
Как именно выпускались сертификаты для существующих доменов — смотрите
в истории; ниже вариант с кратковременной остановкой (простой ~30 секунд).

```bash
cd /home/deploy/sveton
docker compose stop frontend
sudo certbot certonly --standalone -d qulayshahar.uz
docker compose start frontend
```

Проверьте, что автопродление подхватит новый домен:

```bash
sudo certbot renew --dry-run
```

Если продление у вас настроено с хуком перезапуска nginx — новый домен
попадёт в него автоматически, отдельной настройки не требуется.

## 3. Код и настройки

```bash
cd /home/deploy
git clone https://github.com/SeanKOFF/pandus.git
cd pandus
cp .env.production.example .env

python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # ключ Django
openssl rand -base64 24                                          # пароль БД
nano .env
chmod 600 .env
```

В `.env` заполните (остальное уже проставлено):

```
COMPOSE_FILE=docker-compose.yml:docker-compose.shared-nginx.yml
PROXY_NETWORK=sveton_default
DOMAIN=qulayshahar.uz
DJANGO_ALLOWED_HOSTS=qulayshahar.uz
DJANGO_SECRET_KEY=<сгенерированный ключ>
DJANGO_DEBUG=0
DB_PASSWORD=<сгенерированный пароль>
TELEGRAM_BOT_TOKEN=<токен от BotFather>
```

## 4. Запуск стека

В `.env` уже задан `COMPOSE_FILE`, поэтому команды обычные:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f
```

Портов наружу не появится — это правильно. Проверить, что контейнер
виден из nginx:

```bash
docker exec sveton-frontend-1 wget -qO- http://pandus-web:8000/api/points/
```

Должен вернуться JSON. Если нет — контейнер не попал в сеть
`sveton_default`, смотрите `docker inspect pandus-web`.

## 5. Подключение к nginx

Каталог `/etc/nginx/conf.d/` внутри `sveton-frontend-1` **не
примонтирован** — конфиг запечён в образ. Добавьте bind-mount отдельным
файлом, не трогая `default.conf`.

Скопируйте конфиг рядом с проектом sveton:

Конфиг генерируется из `.env`, домен в шаблоне не зашит:

```bash
cd /home/deploy/pandus
./deploy/render-nginx-conf.sh > /home/deploy/sveton/frontend/nginx-pandus.conf
```

В `docker-compose.yml` проекта sveton, в сервисе `frontend`, добавьте
**одну строку** в `volumes`:

```yaml
      - ./frontend/nginx-pandus.conf:/etc/nginx/conf.d/pandus.conf:ro
```

Сначала проверьте конфиг, потом применяйте:

```bash
cd /home/deploy/sveton
docker compose up -d frontend
docker exec sveton-frontend-1 nginx -t
```

Если `nginx -t` ругается — уберите добавленную строку и поднимите
контейнер заново, сайты вернутся.

## 6. Модератор и проверка

```bash
cd /home/deploy/pandus
docker compose exec web python manage.py createsuperuser
```

Проверьте:

- `https://qulayshahar.uz/` — карта
- `https://qulayshahar.uz/admin/` — вход в модерацию
- `https://svetanet.uz/`, `https://chiroqyoq.uz/`, `https://gazyoq.uz/` —
  работают как раньше
- бот отвечает на `/start`

## Откат

Если что-то пошло не так, вернуть сервер в исходное состояние:

```bash
# убрать добавленную строку из docker-compose.yml проекта sveton
cd /home/deploy/sveton && docker compose up -d frontend

cd /home/deploy/pandus && docker compose down -v
```

Соседние проекты при этом не затрагиваются.

## Ресурсы

Стек занимает примерно 400–600 МБ. На момент планирования свободно
было 2.1 ГБ при 2 ГБ swap — запас достаточный. Следить:

```bash
docker stats --no-stream
free -h
```

## Бэкапы

`scripts/backup.sh` рассчитан на имена томов `pandus_pgdata` и
`pandus_photos`. Проверьте фактические имена:

```bash
docker volume ls | grep pandus
```

В cron пользователя deploy:

```
0 3 * * * /home/deploy/pandus/scripts/backup.sh >> /var/log/pandus-backup.log 2>&1
```

## Переезд отсюда

Проект не зашит в этот сервер: всё, что его сюда привязывает, лежит
в `.env` (`COMPOSE_FILE`, `PROXY_NETWORK`, `DOMAIN`). Порядок переезда —
`docs/migration.md`.
