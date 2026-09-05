-- ============================================================
-- Карта доступности — схема БД (PostgreSQL 13+)
-- ============================================================
-- Можно поднять и без PostGIS: используются обычные lat/lng
-- (double precision) + обычные индексы. Если карта разрастётся
-- и понадобятся запросы "точки в видимой области карты" или
-- "ближайшие N точек" — позже добавляем расширение postgis и
-- geography-колонку с GiST-индексом, остальная схема не меняется.

-- ------------------------------------------------------------
-- 1. Категории проблем — таблица, а не enum в коде.
--    Новую категорию добавляет модератор через админку,
--    без деплоя и миграций.
-- ------------------------------------------------------------
CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(50)  NOT NULL UNIQUE,   -- 'no_ramp', 'other' — для кода/API
    label_ru    VARCHAR(100) NOT NULL,          -- 'Нет пандуса' — для интерфейса
    color_hex   VARCHAR(7)   NOT NULL DEFAULT '#546670',
    sort_order  INTEGER      NOT NULL DEFAULT 0,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,  -- скрыть категорию, не удаляя историю
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

INSERT INTO categories (code, label_ru, color_hex, sort_order) VALUES
    ('no_ramp',         'Нет пандуса',            '#C4292E', 10),
    ('broken_sidewalk', 'Разбитый тротуар',       '#B9760A', 20),
    ('blocked',         'Перекрыт проезд',        '#546670', 30),
    ('other',           'Прочее',                 '#7B5EA7', 40);

-- ------------------------------------------------------------
-- 2. Кто прислал репорт (из Telegram). Нужна для антиспама
--    (бан по telegram_user_id) и чтобы уведомить автора,
--    когда его точку опубликовали/устранили — без хранения
--    лишних персональных данных.
-- ------------------------------------------------------------
CREATE TABLE reporters (
    id                SERIAL PRIMARY KEY,
    telegram_user_id  BIGINT      NOT NULL UNIQUE,
    telegram_username VARCHAR(100),
    is_blocked        BOOLEAN     NOT NULL DEFAULT FALSE,
    first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- 3. Модераторы — те, кто работает в админ-панели.
-- ------------------------------------------------------------
CREATE TABLE moderators (
    id          SERIAL PRIMARY KEY,
    full_name   VARCHAR(150) NOT NULL,
    login       VARCHAR(100) NOT NULL UNIQUE,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- 4. Сами репорты.
--
-- Статусы:
--   pending    — только что прислали из бота, ждёт модератора,
--                на публичной карте НЕ виден.
--   published  — модератор одобрил. Живёт на карте БЕССРОЧНО,
--                пока кто-то не переведёт в resolved/rejected.
--   resolved   — проблему устранили. Остаётся на карте (другим
--                цветом), попадает в отчёт для города.
--   rejected   — спам/дубль/не по теме. Скрыт с карты, но
--                запись не удаляется — для истории модерации.
-- ------------------------------------------------------------
CREATE TABLE reports (
    id                    BIGSERIAL PRIMARY KEY,

    reporter_id           INTEGER REFERENCES reporters(id) ON DELETE SET NULL,
    category_id           INTEGER NOT NULL REFERENCES categories(id),

    status                VARCHAR(20) NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'published', 'resolved', 'rejected')),

    lat                   DOUBLE PRECISION NOT NULL,
    lng                   DOUBLE PRECISION NOT NULL,

    description           TEXT,          -- подпись, если пользователь её оставил
    address_hint          TEXT,          -- адрес: вручную от модератора или reverse-geocoding

    -- Фото храним не как публичную ссылку, а как ссылку на объект
    -- во внешнем хранилище (OneDrive и т.п.). Отдаём его через свой
    -- backend-прокси — так неопубликованные фото никогда не утекут
    -- по прямой ссылке, и можно менять хранилище без миграции данных.
    photo_storage         VARCHAR(20)  NOT NULL DEFAULT 'onedrive',
    photo_ref             TEXT         NOT NULL,   -- item id / путь в хранилище
    resolved_photo_ref    TEXT,                    -- необязательное фото "после"

    moderator_id          INTEGER REFERENCES moderators(id),
    moderation_notes      TEXT,                    -- служебные заметки, наружу не показываем
    rejected_reason       TEXT,

    telegram_message_id   BIGINT,        -- для отладки: найти исходное сообщение в боте

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),  -- когда прислали
    moderated_at          TIMESTAMPTZ,                          -- когда одобрили/отклонили
    resolved_at           TIMESTAMPTZ,                          -- когда устранили
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_reports_status        ON reports (status);
CREATE INDEX idx_reports_category      ON reports (category_id);
CREATE INDEX idx_reports_status_cat    ON reports (status, category_id);
CREATE INDEX idx_reports_lat_lng       ON reports (lat, lng);
CREATE INDEX idx_reports_resolved_at   ON reports (resolved_at) WHERE status = 'resolved';

-- ------------------------------------------------------------
-- 5. Автоматический аудит смены статуса.
--    Это и есть "таблица решённых проблем" из вашего вопроса —
--    только универсальная: она пишет вообще все переходы
--    статуса, а "решённые за период" — это просто фильтр по ней.
--    Не нужно вручную дублировать запись при resolve.
-- ------------------------------------------------------------
CREATE TABLE report_status_history (
    id           BIGSERIAL PRIMARY KEY,
    report_id    BIGINT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    old_status   VARCHAR(20),
    new_status   VARCHAR(20) NOT NULL,
    changed_by   INTEGER REFERENCES moderators(id),
    changed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    note         TEXT
);

CREATE INDEX idx_history_report   ON report_status_history (report_id);
CREATE INDEX idx_history_new_st   ON report_status_history (new_status, changed_at);

CREATE OR REPLACE FUNCTION log_report_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO report_status_history (report_id, old_status, new_status, changed_by)
        VALUES (
            NEW.id,
            CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.status END,
            NEW.status,
            NEW.moderator_id
        );

        IF NEW.status IN ('published', 'rejected') THEN
            NEW.moderated_at := now();
        END IF;
        IF NEW.status = 'resolved' THEN
            NEW.resolved_at := now();
        END IF;
    END IF;

    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reports_status_log
    BEFORE INSERT OR UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION log_report_status_change();

-- ------------------------------------------------------------
-- 6. Публичные представления.
--
--    v_public_map     — то, что реально уходит на карту и в API
--                        для фронтенда. Никаких данных о репортёре,
--                        модераторе или внутренних заметках.
--    v_resolved_log    — готовая выгрузка для отчёта городу
--                        (устранённые проблемы за период).
-- ------------------------------------------------------------
CREATE VIEW v_public_map AS
SELECT
    r.id,
    r.lat,
    r.lng,
    c.code           AS category_code,
    c.label_ru       AS category_label,
    c.color_hex      AS category_color,
    r.status,                          -- 'published' или 'resolved'
    r.address_hint,
    r.description,
    r.created_at,
    r.resolved_at
FROM reports r
JOIN categories c ON c.id = r.category_id
WHERE r.status IN ('published', 'resolved');

CREATE VIEW v_resolved_log AS
SELECT
    r.id,
    c.label_ru       AS category_label,
    r.address_hint,
    r.lat,
    r.lng,
    r.created_at     AS reported_at,
    r.resolved_at,
    (r.resolved_at - r.created_at)  AS time_to_fix,
    m.full_name      AS resolved_by
FROM reports r
JOIN categories c ON c.id = r.category_id
LEFT JOIN moderators m ON m.id = r.moderator_id
WHERE r.status = 'resolved'
ORDER BY r.resolved_at DESC;
