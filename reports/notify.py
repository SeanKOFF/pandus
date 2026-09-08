"""Уведомление автора заявки о смене статуса.

Отправляем синхронно, прямым вызовом Telegram API: очереди в проекте нет,
а сообщений — единицы в день. Любая ошибка глушится: недоставленное
уведомление не должно ронять сохранение заявки.

Язык берётся из Reporter.language и передаётся явно — по той же причине,
что и в боте: активный язык Django потоко-локальный и здесь не годится.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

NOTIFY_TEXTS = {
    "published": {
        "ru": "Ваша заявка опубликована на карте: {url}",
        "uz": "Arizangiz xaritada e’lon qilindi: {url}",
    },
    "resolved": {
        "ru": "Проблема из вашей заявки отмечена как устранённая. "
              "Спасибо, что сообщили.",
        "uz": "Arizangizdagi muammo bartaraf etilgan deb belgilandi. "
              "Xabar berganingiz uchun rahmat.",
    },
}


def notify_status(report, new_status):
    """Сообщает автору о публикации или устранении. Отказ не уведомляем:
    отказ без объяснения обижает, а объяснение пишется руками."""
    texts = NOTIFY_TEXTS.get(new_status)
    if not texts or not settings.TELEGRAM_BOT_TOKEN:
        return

    lang = report.reporter.language if report.reporter.language in texts else "ru"
    text = texts[lang].format(url=settings.SITE_URL)

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": report.reporter.telegram_user_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=5,
        )
        # Телеграм отвечает 200 и на отказ (например, автор заблокировал
        # бота), поэтому исключения недостаточно — смотрим тело ответа.
        if not response.json().get("ok"):
            logger.warning(
                "Telegram отклонил уведомление по заявке #%s: %s",
                report.pk, response.text[:200],
            )
    except (requests.RequestException, ValueError):
        logger.warning("Не удалось уведомить автора заявки #%s", report.pk)
