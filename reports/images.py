"""Нормализация входящих фотографий.

Зачем: снимки приходят разного размера и веса — от 800px до
многомегапиксельных. Без приведения к общему знаменателю карта с сотней
точек тянула бы десятки мегабайт, а вёрстка попапов «прыгала» бы.

Что делает normalize():
  * поворачивает по EXIF-ориентации (иначе фото с телефона лежит на боку);
  * приводит к RGB и JPEG (PNG/HEIC/прозрачность отсекаются);
  * ограничивает длинную сторону;
  * пересохраняет БЕЗ метаданных — вместе с ними уходят и GPS-координаты
    съёмки, которые иначе утекли бы в публичный доступ вместе с файлом.
"""

import io

from PIL import Image, ImageOps

FULL_MAX_SIDE = 1600
FULL_QUALITY = 82

THUMB_MAX_SIDE = 400
THUMB_QUALITY = 78


def _encode(img: Image.Image, max_side: int, quality: int) -> bytes:
    img = ImageOps.exif_transpose(img)          # учесть поворот камеры
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)

    buf = io.BytesIO()
    # Новый объект Image без exif — метаданные не переносятся
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def normalize(data: bytes) -> tuple[bytes, bytes]:
    """Возвращает (полное фото, миниатюра). Бросает OSError, если это не картинка."""
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        full = _encode(img.copy(), FULL_MAX_SIDE, FULL_QUALITY)
        thumb = _encode(img.copy(), THUMB_MAX_SIDE, THUMB_QUALITY)
    return full, thumb
