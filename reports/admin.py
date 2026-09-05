from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import Category, Report, Reporter, ReportStatusHistory

admin.site.site_header = "Pandus — модерация"
admin.site.site_title = "Pandus"
admin.site.index_title = "Заявки о проблемных местах"


STATUS_COLORS = {
    Report.Status.PENDING: "#B9760A",
    Report.Status.PUBLISHED: "#C4292E",
    Report.Status.RESOLVED: "#3F7D53",
    Report.Status.REJECTED: "#8A8A8A",
}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("label_ru", "code", "color_swatch", "sort_order", "is_active", "report_count")
    list_editable = ("sort_order", "is_active")
    search_fields = ("label_ru", "code")

    @admin.display(description="Цвет")
    def color_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:14px;height:14px;'
            'border-radius:50%;background:{};border:1px solid #ccc"></span> {}',
            obj.color_hex, obj.color_hex,
        )

    @admin.display(description="Заявок")
    def report_count(self, obj):
        return obj.reports.count()


@admin.register(Reporter)
class ReporterAdmin(admin.ModelAdmin):
    list_display = ("__str__", "telegram_user_id", "is_blocked", "report_count", "first_seen_at")
    list_filter = ("is_blocked",)
    search_fields = ("telegram_username", "telegram_user_id")
    actions = ("block", "unblock")

    @admin.display(description="Заявок")
    def report_count(self, obj):
        return obj.reports.count()

    @admin.action(description="Заблокировать")
    def block(self, request, queryset):
        n = queryset.update(is_blocked=True)
        self.message_user(request, f"Заблокировано: {n}")

    @admin.action(description="Разблокировать")
    def unblock(self, request, queryset):
        n = queryset.update(is_blocked=False)
        self.message_user(request, f"Разблокировано: {n}")


class StatusHistoryInline(admin.TabularInline):
    model = ReportStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("old_status", "new_status", "changed_by", "changed_at", "note")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "photo_thumb", "category", "status_badge", "address_hint", "created_at", "age")
    list_filter = ("status", "category", "created_at")
    search_fields = ("address_hint", "description", "id")
    date_hierarchy = "created_at"
    list_select_related = ("category", "reporter")
    inlines = (StatusHistoryInline,)
    actions = ("publish", "mark_resolved", "reject")
    readonly_fields = ("created_at", "moderated_at", "resolved_at", "updated_at",
                       "photo_preview", "map_link", "reporter", "telegram_message_id")

    fieldsets = (
        ("Модерация", {
            "fields": ("status", "category", "moderation_notes", "rejected_reason", "moderator"),
        }),
        ("Место", {
            "fields": ("photo_preview", "map_link", "lat", "lng", "address_hint", "description"),
        }),
        ("Фото после устранения", {
            "classes": ("collapse",),
            "fields": ("photo_ref", "photo_storage", "resolved_photo_ref"),
        }),
        ("Служебное", {
            "classes": ("collapse",),
            "fields": ("reporter", "telegram_message_id",
                       "created_at", "moderated_at", "resolved_at", "updated_at"),
        }),
    )

    # --- Отображение -------------------------------------------------

    @admin.display(description="Фото")
    def photo_thumb(self, obj):
        if not obj.photo_ref:
            return "—"
        return format_html(
            '<img src="/media/{}/" style="width:64px;height:48px;object-fit:cover;'
            'border-radius:4px" loading="lazy">', obj.pk,
        )

    @admin.display(description="Фото места")
    def photo_preview(self, obj):
        if not obj.photo_ref:
            return "Фото не приложено"
        return format_html(
            '<img src="/media/{}/" style="max-width:520px;border-radius:8px">', obj.pk,
        )

    @admin.display(description="Статус")
    def status_badge(self, obj):
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 9px;'
            'border-radius:10px;font-size:11px">{}</span>',
            STATUS_COLORS.get(obj.status, "#666"), obj.get_status_display(),
        )

    @admin.display(description="На карте")
    def map_link(self, obj):
        return format_html(
            '<a href="https://www.openstreetmap.org/?mlat={}&mlon={}#map=19/{}/{}" '
            'target="_blank" rel="noopener">Открыть {}, {} в OpenStreetMap</a>',
            obj.lat, obj.lng, obj.lat, obj.lng, obj.lat, obj.lng,
        )

    @admin.display(description="Висит")
    def age(self, obj):
        end = obj.resolved_at or timezone.now()
        days = (end - obj.created_at).days
        if obj.status == Report.Status.RESOLVED:
            return f"устранено за {days} дн."
        return f"{days} дн."

    # --- Действия ----------------------------------------------------

    def _switch(self, request, queryset, status, verb):
        changed = 0
        for report in queryset:
            if report.status == status:
                continue
            report.status = status
            report.moderator = request.user
            report.save()
            changed += 1
        self.message_user(request, f"{verb}: {changed}", messages.SUCCESS)

    @admin.action(description="Опубликовать на карте")
    def publish(self, request, queryset):
        self._switch(request, queryset, Report.Status.PUBLISHED, "Опубликовано")

    @admin.action(description="Отметить устранённым")
    def mark_resolved(self, request, queryset):
        self._switch(request, queryset, Report.Status.RESOLVED, "Отмечено устранённым")

    @admin.action(description="Отклонить")
    def reject(self, request, queryset):
        self._switch(request, queryset, Report.Status.REJECTED, "Отклонено")

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data and not obj.moderator:
            obj.moderator = request.user
        super().save_model(request, obj, form, change)


@admin.register(ReportStatusHistory)
class ReportStatusHistoryAdmin(admin.ModelAdmin):
    """Журнал для отчётности: фильтр new_status='resolved' + период дат
    даёт готовую выгрузку устранённых проблем."""

    list_display = ("report", "old_status", "new_status", "changed_by", "changed_at")
    list_filter = ("new_status", "changed_at")
    date_hierarchy = "changed_at"
    search_fields = ("report__id", "report__address_hint")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
