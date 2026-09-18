"""Публичный API карты.

Отдаёт только опубликованные и устранённые точки. Данные автора заявки,
модератора и служебные заметки наружу не уходят — состав полей задан
явно в _serialize(), а не сериализацией модели целиком.
"""

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from .models import Category, Report
from .storage import FULL, THUMB, get_storage


def _serialize(report):
    return {
        "id": report.id,
        "lat": report.lat,
        "lng": report.lng,
        "category": report.category.code,
        "category_label": report.category.label(),
        "color": report.category.color_hex,
        "status": report.status,
        "address": report.address_hint,
        "description": report.description,
        "photo_url": f"/media/{report.id}/" if report.photo_ref else None,
        "photo_thumb_url": f"/media/{report.id}/?size=thumb" if report.photo_ref else None,
        "created_at": report.created_at.isoformat(),
        "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None,
    }


@require_GET
def public_points(request):
    """GET /api/points/ — точки для карты.

    Необязательные фильтры: ?category=no_ramp&status=published
    """
    qs = (
        Report.objects
        .filter(status__in=Report.PUBLIC_STATUSES)
        .select_related("category")
    )

    category = request.GET.get("category")
    if category:
        qs = qs.filter(category__code=category)

    status = request.GET.get("status")
    if status in dict(Report.Status.choices) and status in Report.PUBLIC_STATUSES:
        qs = qs.filter(status=status)

    return JsonResponse({
        "count": qs.count(),
        "points": [_serialize(r) for r in qs],
    })


@require_GET
def public_categories(request):
    """GET /api/categories/ — список категорий для легенды карты."""
    qs = Category.objects.filter(is_active=True)
    return JsonResponse({
        "categories": [
            {
                "code": c.code,
                "label": c.label(),
                "color": c.color_hex,
                "count": c.reports.filter(status__in=Report.PUBLIC_STATUSES).count(),
            }
            for c in qs
        ]
    })


@require_GET
def photo(request, report_id):
    """GET /media/<report_id>/ — прокси к хранилищу фотографий.

    Фото неопубликованной заявки отдаётся только залогиненному
    сотруднику (для превью в админке). Публике видны снимки
    только опубликованных и устранённых точек.
    """
    try:
        report = Report.objects.get(pk=report_id)
    except Report.DoesNotExist:
        raise Http404

    if not report.is_public and not request.user.is_staff:
        raise Http404

    if not report.photo_ref:
        raise Http404

    variant = THUMB if request.GET.get("size") == "thumb" else FULL
    try:
        data = get_storage(report.photo_storage).fetch(report.photo_ref, variant)
    except (FileNotFoundError, ValueError, NotImplementedError):
        raise Http404

    import io
    response = FileResponse(io.BytesIO(data), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600" if not report.is_public else "public, max-age=86400"
    return response


def map_page(request):
    """GET / — публичная карта. Отдаётся с того же домена, что и API,
    поэтому CORS не нужен.

    ?lang=uz переключает язык и запоминает выбор в cookie, чтобы при
    следующем заходе человек попал сразу на свою версию.
    """
    lang = request.GET.get("lang")
    if lang in dict(settings.LANGUAGES):
        response = redirect("map")
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME, lang,
            max_age=365 * 24 * 3600, samesite="Lax",
        )
        return response

    # Строки для JavaScript: в шаблоне их не собрать, а дублировать
    # переводы в JS-коде значило бы вести два словаря вместо одного
    js_strings = {
        "loading": _("Загружаем точки…"),
        "empty": _("Пока ни одной опубликованной точки. Отправьте место через бота — "
                   "после проверки оно появится здесь."),
        "error": _("Не удалось загрузить точки. Обновите страницу."),
        "no_photo": _("Фото не приложено"),
        "photo_unavailable": _("Фото недоступно"),
        "reported": _("Сообщено"),
        "resolved": _("Устранено"),
    }
    return render(request, "reports/map.html", {"js_strings": js_strings})
