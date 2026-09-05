"""Публичный API карты.

Отдаёт только опубликованные и устранённые точки. Данные автора заявки,
модератора и служебные заметки наружу не уходят — состав полей задан
явно в _serialize(), а не сериализацией модели целиком.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Category, Report


def _serialize(report):
    return {
        "id": report.id,
        "lat": report.lat,
        "lng": report.lng,
        "category": report.category.code,
        "category_label": report.category.label_ru,
        "color": report.category.color_hex,
        "status": report.status,
        "address": report.address_hint,
        "description": report.description,
        "photo_url": f"/media/{report.id}/" if report.photo_ref else None,
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
                "label": c.label_ru,
                "color": c.color_hex,
                "count": c.reports.filter(status__in=Report.PUBLIC_STATUSES).count(),
            }
            for c in qs
        ]
    })
