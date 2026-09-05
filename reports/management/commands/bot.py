"""Telegram-бот приёма заявок.

Запуск:  python manage.py bot

Бот работает внутри Django-процесса и пишет напрямую через ORM —
отдельный API для приёма заявок не нужен, как и его авторизация.

Сценарий:
    /start → геолокация → фото → категория → (описание) → заявка создана
Заявка попадает в статус «На модерации» и на карте не появляется,
пока модератор её не опубликует.
"""

import asyncio
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)

from reports.models import Category, Report, Reporter
from reports.storage import get_storage

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 12 * 1024 * 1024


class Flow(StatesGroup):
    waiting_location = State()
    waiting_photo = State()
    waiting_category = State()
    waiting_description = State()


# --- Обёртки ORM для async-контекста -------------------------------

@sync_to_async
def get_or_create_reporter(tg_user):
    reporter, _ = Reporter.objects.get_or_create(
        telegram_user_id=tg_user.id,
        defaults={"telegram_username": tg_user.username or ""},
    )
    if tg_user.username and reporter.telegram_username != tg_user.username:
        reporter.telegram_username = tg_user.username
        reporter.save(update_fields=["telegram_username"])
    return reporter


@sync_to_async
def active_categories():
    return list(Category.objects.filter(is_active=True))


@sync_to_async
def save_photo(data: bytes) -> tuple[str, str]:
    storage = get_storage()
    return storage.save(data), storage.name


@sync_to_async
def create_report(reporter, category_id, lat, lng, photo_ref, storage_name, description, message_id):
    report = Report.objects.create(
        reporter=reporter,
        category_id=category_id,
        lat=lat,
        lng=lng,
        photo_ref=photo_ref,
        photo_storage=storage_name,
        description=description or "",
        telegram_message_id=message_id,
    )
    return report.id


@sync_to_async
def count_user_reports(reporter):
    return reporter.reports.count()


# --- Клавиатуры ----------------------------------------------------

def location_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Отправить геолокацию", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def categories_kb(categories):
    rows = [
        [InlineKeyboardButton(text=c.label_ru, callback_data=f"cat:{c.id}")]
        for c in categories
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_desc")]
    ])


# --- Хендлеры ------------------------------------------------------

dp = Dispatcher(storage=MemoryStorage())


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    reporter = await get_or_create_reporter(message.from_user)
    if reporter.is_blocked:
        await message.answer("Приём заявок с этого аккаунта приостановлен.")
        return

    await state.clear()
    await state.set_state(Flow.waiting_location)
    await message.answer(
        "Здесь можно сообщить о месте, где нет условий для проезда: "
        "отсутствует пандус, разбит тротуар, перекрыт проход.\n\n"
        "После проверки модератором точка появится на общей карте города.\n\n"
        "Шаг 1 из 3. Отправьте геолокацию места — кнопкой ниже "
        "или через скрепку → «Геопозиция».",
        reply_markup=location_kb(),
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Заявка отменена. Чтобы начать заново — /start",
                         reply_markup=ReplyKeyboardRemove())


@dp.message(Command("my"))
async def cmd_my(message: Message):
    reporter = await get_or_create_reporter(message.from_user)
    total = await count_user_reports(reporter)
    await message.answer(f"Вы отправили заявок: {total}")


@dp.message(Flow.waiting_location, F.location)
async def got_location(message: Message, state: FSMContext):
    await state.update_data(lat=message.location.latitude, lng=message.location.longitude)
    await state.set_state(Flow.waiting_photo)
    await message.answer(
        "Шаг 2 из 3. Теперь пришлите фотографию места.\n\n"
        "Постарайтесь, чтобы в кадр не попадали лица людей и "
        "номера автомобилей — снимки публикуются открыто.",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Flow.waiting_location)
async def need_location(message: Message):
    await message.answer("Нужна геолокация места. Нажмите кнопку ниже или отправьте "
                         "точку через скрепку → «Геопозиция».",
                         reply_markup=location_kb())


@dp.message(Flow.waiting_photo, F.photo)
async def got_photo(message: Message, state: FSMContext, bot: Bot):
    photo = message.photo[-1]  # максимальное доступное разрешение
    if photo.file_size and photo.file_size > MAX_PHOTO_BYTES:
        await message.answer("Файл слишком большой. Пришлите снимок поменьше.")
        return

    await message.answer("Загружаю фото…")
    buffer = await bot.download(photo.file_id)
    try:
        ref, storage_name = await save_photo(buffer.read())
    except OSError:
        await message.answer("Не удалось обработать изображение. "
                             "Попробуйте прислать другой снимок.")
        return

    await state.update_data(photo_ref=ref, storage=storage_name, message_id=message.message_id)
    await state.set_state(Flow.waiting_category)

    categories = await active_categories()
    await message.answer("Шаг 3 из 3. Выберите, в чём проблема:",
                         reply_markup=categories_kb(categories))


@dp.message(Flow.waiting_photo, F.document)
async def photo_as_document(message: Message):
    await message.answer("Пришлите снимок именно как фото, а не файлом — "
                         "так он корректно отобразится на карте.")


@dp.message(Flow.waiting_photo)
async def need_photo(message: Message):
    await message.answer("Нужна фотография места. Пришлите снимок или отмените заявку: /cancel")


@dp.callback_query(Flow.waiting_category, F.data.startswith("cat:"))
async def got_category(call: CallbackQuery, state: FSMContext):
    await state.update_data(category_id=int(call.data.split(":")[1]))
    await state.set_state(Flow.waiting_description)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    await call.message.answer(
        "Добавьте короткое описание — ориентир, адрес, детали. "
        "Или пропустите этот шаг.",
        reply_markup=skip_kb(),
    )


async def _finish(target_message, state, from_user, description):
    data = await state.get_data()
    reporter = await get_or_create_reporter(from_user)
    report_id = await create_report(
        reporter, data["category_id"], data["lat"], data["lng"],
        data["photo_ref"], data["storage"], description, data.get("message_id"),
    )
    await state.clear()
    await target_message.answer(
        f"Заявка №{report_id} принята и отправлена на проверку.\n\n"
        "После одобрения модератором точка появится на карте города. "
        "Чтобы сообщить о другом месте — /start"
    )


@dp.callback_query(Flow.waiting_description, F.data == "skip_desc")
async def skip_description(call: CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    await _finish(call.message, state, call.from_user, "")


@dp.message(Flow.waiting_description, F.text)
async def got_description(message: Message, state: FSMContext):
    await _finish(message, state, message.from_user, message.text[:1000])


@dp.message()
async def fallback(message: Message):
    await message.answer("Чтобы сообщить о проблемном месте, начните с команды /start")


class Command(BaseCommand):
    help = "Запускает Telegram-бота приёма заявок"

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError(
                "TELEGRAM_BOT_TOKEN не задан. Получите токен у @BotFather "
                "и добавьте его в файл .env"
            )

        logging.basicConfig(level=logging.INFO)
        self.stdout.write(self.style.SUCCESS("Бот запущен. Остановить — Ctrl+C"))

        bot = Bot(token=token)
        try:
            asyncio.run(dp.start_polling(bot))
        except KeyboardInterrupt:
            self.stdout.write("Бот остановлен")
