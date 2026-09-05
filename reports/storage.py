"""Абстракция хранилища фотографий.

Backend выбирается переменной PHOTO_STORAGE в .env:
  local     — файлы в папке на диске (разработка и старт проекта)
  onedrive  — Microsoft Graph API (планируется)

Каждое фото хранится в двух вариантах: полное (до 1600px) и миниатюра
(до 400px). Миниатюра идёт в списки админки и всплывающие подсказки на
карте, полное — в карточку заявки. Имя миниатюры выводится из ref по
соглашению «<имя>_thumb.jpg», поэтому в модели по-прежнему одно поле.

Модель хранит не URL, а ref — непрозрачный идентификатор внутри
хранилища. Наружу фото отдаётся только через /media/<report_id>/,
поэтому неопубликованные снимки недоступны по прямой ссылке.
"""

import uuid
from pathlib import Path

from django.conf import settings

from .images import normalize

FULL = "full"
THUMB = "thumb"


def _thumb_name(ref: str) -> str:
    stem, _, ext = ref.rpartition(".")
    return f"{stem}_thumb.{ext}"


class BaseStorage:
    name = "base"

    def save(self, data: bytes) -> str:
        """Нормализует изображение, кладёт оба варианта, возвращает ref."""
        raise NotImplementedError

    def fetch(self, ref: str, variant: str = FULL) -> bytes:
        raise NotImplementedError

    def delete(self, ref: str) -> None:
        raise NotImplementedError


class LocalStorage(BaseStorage):
    """Файлы в PHOTO_LOCAL_ROOT. Папка намеренно вне static/ —
    Django её не раздаёт, доступ только через прокси-вью."""

    name = "local"

    def __init__(self, root=None):
        self.root = Path(root or settings.PHOTO_LOCAL_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, ref: str) -> Path:
        path = (self.root / ref).resolve()
        # Защита от обхода каталога, если ref когда-то придёт извне
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("Некорректная ссылка на файл")
        return path

    def save(self, data: bytes) -> str:
        full, thumb = normalize(data)
        ref = f"{uuid.uuid4().hex}.jpg"
        self._path(ref).write_bytes(full)
        self._path(_thumb_name(ref)).write_bytes(thumb)
        return ref

    def fetch(self, ref: str, variant: str = FULL) -> bytes:
        name = _thumb_name(ref) if variant == THUMB else ref
        try:
            return self._path(name).read_bytes()
        except FileNotFoundError:
            if variant == THUMB:      # старые файлы без миниатюры
                return self._path(ref).read_bytes()
            raise

    def delete(self, ref: str) -> None:
        self._path(ref).unlink(missing_ok=True)
        self._path(_thumb_name(ref)).unlink(missing_ok=True)


class OneDriveStorage(BaseStorage):
    """Заглушка. Будет заливать в OneDrive через Microsoft Graph API,
    ref = item id. Интерфейс тот же, поэтому бот и админка
    при переключении не меняются."""

    name = "onedrive"

    def save(self, data: bytes) -> str:
        raise NotImplementedError("OneDrive-хранилище ещё не подключено")

    def fetch(self, ref: str, variant: str = FULL) -> bytes:
        raise NotImplementedError("OneDrive-хранилище ещё не подключено")


_BACKENDS = {"local": LocalStorage, "onedrive": OneDriveStorage}


def get_storage(name: str = None) -> BaseStorage:
    name = name or settings.PHOTO_STORAGE
    try:
        return _BACKENDS[name]()
    except KeyError:
        raise ValueError(f"Неизвестное хранилище: {name}")
