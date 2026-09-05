# Развёртывание на сервере

Схема: Docker Compose поднимает четыре контейнера — PostgreSQL, сайт
(gunicorn), Telegram-бот и Caddy. Caddy сам получает сертификат
Let's Encrypt и продлевает его, certbot не нужен.

Сайт и бот работают из одного образа, но это отдельные процессы: если
бот упадёт, карта продолжит работать. Фотографии лежат на общем томе,
бот пишет — сайт отдаёт.

## Что нужно заранее

- VPS: 2 ГБ памяти хватает с запасом, 1 ГБ — впритык. Ubuntu 22.04/24.04.
- Домен, у которого A-запись указывает на IP сервера. Без домена Caddy
  не выпустит сертификат.
- Токен бота от @BotFather.

## 1. Подготовка сервера

```bash
ssh root@IP_СЕРВЕРА

apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh

# Отдельный пользователь: работать под root не нужно
adduser --disabled-password --gecos "" pandus
usermod -aG docker pandus
mkdir -p /home/pandus/.ssh
cp ~/.ssh/authorized_keys /home/pandus/.ssh/
chown -R pandus:pandus /home/pandus/.ssh
chmod 700 /home/pandus/.ssh
```

Файрвол — открыты только SSH и веб:

```bash
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable
```

## 2. Код на сервере

```bash
su - pandus
git clone https://github.com/SeanKOFF/pandus.git
cd pandus
```

Репозиторий публичный, поэтому клонируется по HTTPS без ключей. Если
сделаете его приватным — понадобится deploy key.

## 3. Настройки

```bash
cp .env.production.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # ключ Django
openssl rand -base64 24                                          # пароль БД
nano .env
```

Заполните `DOMAIN`, `DJANGO_ALLOWED_HOSTS` (тот же домен),
`DJANGO_SECRET_KEY`, `DB_PASSWORD`, `TELEGRAM_BOT_TOKEN`.
`DJANGO_DEBUG` оставьте `0`.

Проверьте права: `.env` содержит все секреты проекта.

```bash
chmod 600 .env
```

## 4. Запуск

```bash
docker compose up -d --build
docker compose logs -f
```

Миграции и сборка статики выполняются автоматически при старте
контейнера `web`. Caddy получит сертификат за 10–30 секунд — если
A-запись домена ещё не разошлась по DNS, в логах будет ошибка выпуска;
подождите и перезапустите: `docker compose restart caddy`.

Создайте модератора:

```bash
docker compose exec web python manage.py createsuperuser
```

Откройте `https://ваш-домен/admin/` — должна быть форма входа.

## 5. Проверка после запуска

```bash
docker compose exec web python manage.py check --deploy
```

Вручную:

- `http://домен` редиректит на `https://`
- карта открывается на `https://домен/`
- бот отвечает на `/start`
- фото неопубликованной заявки по прямой ссылке даёт 404 в анонимном окне

## 6. Резервные копии

```bash
sudo mkdir -p /var/backups/pandus
sudo chown pandus:pandus /var/backups/pandus
crontab -e
```

Строка в crontab:

```
0 3 * * * /home/pandus/pandus/scripts/backup.sh >> /var/log/pandus-backup.log 2>&1
```

Копии на том же сервере не спасают от его потери — настройте выгрузку
`/var/backups/pandus` наружу (rclone, scp на другой хост, объектное
хранилище).

**Восстановление проверьте один раз вручную.** Непроверенный бэкап
бэкапом не считается:

```bash
gunzip -c /var/backups/pandus/db_ДАТА.sql.gz | \
  docker compose exec -T db psql -U pandus pandus
```

## Обновление версии

```bash
cd ~/pandus
git pull
docker compose up -d --build
```

Миграции применятся сами. Простой — несколько секунд.

## Полезные команды

| Команда | Что делает |
|---|---|
| `docker compose ps` | статус контейнеров |
| `docker compose logs -f bot` | логи бота |
| `docker compose logs -f web` | логи сайта |
| `docker compose restart bot` | перезапустить бота |
| `docker compose exec web python manage.py changepassword ЛОГИН` | сменить пароль модератора |
| `docker compose exec db psql -U pandus pandus` | консоль базы |
| `docker compose down` | остановить всё (данные в томах сохранятся) |

## Если что-то не работает

**Caddy не выпускает сертификат.** Проверьте `dig ваш-домен +short` —
должен вернуть IP сервера. Порты 80 и 443 должны быть открыты, иначе
Let's Encrypt не подтвердит владение доменом.

**Бот не отвечает.** `docker compose logs bot`. Частая причина — пустой
или неверный `TELEGRAM_BOT_TOKEN`.

**502 от Caddy.** Контейнер `web` не поднялся: `docker compose logs web`.
Обычно это падение на проверке `DJANGO_SECRET_KEY` — ключ не заполнен.

**Фото не открываются.** Убедитесь, что у `web` и `bot` смонтирован один
и тот же том `photos` — иначе бот пишет в одно место, а сайт читает
из другого.
