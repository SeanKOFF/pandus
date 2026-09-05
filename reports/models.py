from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.Model):
    """Категория проблемы. Хранится в БД, а не в коде, — новую категорию
    модератор добавляет через админку, без деплоя."""

    code = models.SlugField("Код", max_length=50, unique=True)
    label_ru = models.CharField("Название", max_length=100)
    color_hex = models.CharField("Цвет на карте", max_length=7, default="#546670")
    sort_order = models.IntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.label_ru


class Reporter(models.Model):
    """Автор заявки из Telegram. Нужен для антиспама и чтобы уведомить
    человека, когда его точку опубликовали или проблему устранили."""

    telegram_user_id = models.BigIntegerField("Telegram ID", unique=True)
    telegram_username = models.CharField("Username", max_length=100, blank=True)
    is_blocked = models.BooleanField("Заблокирован", default=False)
    first_seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "автор заявки"
        verbose_name_plural = "авторы заявок"

    def __str__(self):
        return self.telegram_username or str(self.telegram_user_id)


class Report(models.Model):
    """Заявка о проблемном месте.

    Жизненный цикл: PENDING -> PUBLISHED -> RESOLVED / REJECTED.
    Опубликованная точка живёт на карте бессрочно, пока статус
    не сменят вручную. Ничего не удаляется — REJECTED тоже остаётся
    в базе для истории модерации.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "На модерации"
        PUBLISHED = "published", "Опубликовано"
        RESOLVED = "resolved", "Устранено"
        REJECTED = "rejected", "Отклонено"

    PUBLIC_STATUSES = (Status.PUBLISHED, Status.RESOLVED)

    reporter = models.ForeignKey(
        Reporter, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Автор", related_name="reports",
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT,
        verbose_name="Категория", related_name="reports",
    )
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )

    lat = models.FloatField("Широта")
    lng = models.FloatField("Долгота")

    description = models.TextField("Описание от автора", blank=True)
    address_hint = models.TextField("Адрес", blank=True)

    # Не прямая ссылка, а идентификатор объекта в хранилище (OneDrive item id).
    # Фото отдаётся через собственный прокси-эндпоинт, поэтому неопубликованные
    # снимки недоступны снаружи, а смена хранилища не ломает ссылки в базе.
    photo_storage = models.CharField("Хранилище", max_length=20, default="onedrive")
    photo_ref = models.TextField("Ссылка на фото в хранилище")
    resolved_photo_ref = models.TextField("Фото после устранения", blank=True)

    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Модератор", related_name="moderated_reports",
    )
    moderation_notes = models.TextField("Заметки модератора", blank=True)
    rejected_reason = models.TextField("Причина отклонения", blank=True)

    telegram_message_id = models.BigIntegerField(null=True, blank=True)

    created_at = models.DateTimeField("Прислано", auto_now_add=True)
    moderated_at = models.DateTimeField("Промодерировано", null=True, blank=True)
    resolved_at = models.DateTimeField("Устранено", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "заявка"
        verbose_name_plural = "заявки"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "category"]),
            models.Index(fields=["lat", "lng"]),
        ]

    def __str__(self):
        return f"#{self.pk} {self.category} — {self.address_hint or 'без адреса'}"

    @property
    def is_public(self):
        return self.status in self.PUBLIC_STATUSES

    @property
    def time_to_fix(self):
        """Сколько провисела проблема до устранения — метрика для отчёта городу."""
        if self.resolved_at:
            return self.resolved_at - self.created_at
        return None

    def save(self, *args, **kwargs):
        """Проставляет служебные даты и пишет историю смены статуса."""
        old_status = None
        if self.pk:
            old_status = Report.objects.filter(pk=self.pk).values_list("status", flat=True).first()

        now = timezone.now()
        if old_status != self.status:
            if self.status in (self.Status.PUBLISHED, self.Status.REJECTED) and not self.moderated_at:
                self.moderated_at = now
            if self.status == self.Status.RESOLVED and not self.resolved_at:
                self.resolved_at = now

        super().save(*args, **kwargs)

        if old_status != self.status:
            ReportStatusHistory.objects.create(
                report=self,
                old_status=old_status or "",
                new_status=self.status,
                changed_by=self.moderator,
            )


class ReportStatusHistory(models.Model):
    """Журнал смены статусов. Заменяет отдельную «таблицу решённых проблем»:
    отчёт об устранённом за период — это фильтр по new_status='resolved'."""

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE,
        verbose_name="Заявка", related_name="history",
    )
    old_status = models.CharField("Было", max_length=20, blank=True)
    new_status = models.CharField("Стало", max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Кто изменил",
    )
    changed_at = models.DateTimeField("Когда", auto_now_add=True)
    note = models.TextField("Примечание", blank=True)

    class Meta:
        verbose_name = "запись истории"
        verbose_name_plural = "история статусов"
        ordering = ["-changed_at"]

    def __str__(self):
        return f"#{self.report_id}: {self.old_status or '—'} → {self.new_status}"
