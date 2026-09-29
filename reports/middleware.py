"""Язык админки не зависит от языка публичной карты.

Посетитель переключает карту на узбекский — cookie языка выставляется
на весь сайт, включая /admin/. В результате встроенные строки Django
показывались по-узбекски, а подписи моделей (они заданы в коде
по-русски) оставались русскими: интерфейс модерации получался
наполовину на одном языке, наполовину на другом.

Админка — внутренний инструмент, её язык задаётся отдельной
переменной ADMIN_LANGUAGE_CODE и от выбора на карте не зависит.
"""

from django.conf import settings
from django.utils import translation


class AdminLocaleMiddleware:
    """Фиксирует язык в админке. Ставится ПОСЛЕ LocaleMiddleware,
    чтобы перебить язык, выбранный посетителем на карте."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_language = getattr(settings, "ADMIN_LANGUAGE_CODE", "ru")

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            with translation.override(self.admin_language):
                request.LANGUAGE_CODE = self.admin_language
                return self.get_response(request)
        return self.get_response(request)
