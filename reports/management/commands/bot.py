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

from reports.bot_texts import t
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
def set_language(reporter, lang):
    reporter.language = lang
    reporter.language_chosen = True
    reporter.save(update_fields=["language", "language_chosen"])


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


@sync_to_async
def rate_limit_exceeded(reporter):
    """Ограничивает поток заявок от одного человека.

    Без этого один пользователь за вечер способен забить карту сотнями
    точек, и модерация встанет. Лимиты настраиваются в .env.
    """
    from datetime import timedelta

    from django.utils import timezone as tz

    lang = reporter.language
    now = tz.now()
    per_hour = reporter.reports.filter(created_at__gte=now - timedelta(hours=1)).count()
    if per_hour >= settings.REPORTS_PER_HOUR:
        return t("limit_hour", lang, n=per_hour)

    per_day = reporter.reports.filter(created_at__gte=now - timedelta(days=1)).count()
    if per_day >= settings.REPORTS_PER_DAY:
        return t("limit_day", lang, n=per_day)

    return None


# --- Клавиатуры ----------------------------------------------------

def location_kb(lang):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("send_location_btn", lang), request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def categories_kb(categories, lang):
    rows = [
        [InlineKeyboardButton(text=c.label(lang), callback_data=f"cat:{c.id}")]
        for c in categories
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("skip_btn", lang), callback_data="skip_desc")]
    ])


def language_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="O‘zbekcha", callback_data="lang:uz"),
    ]])


# --- Хендлеры ------------------------------------------------------

dp = Dispatcher(storage=MemoryStorage())


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    reporter = await get_or_create_reporter(message.from_user)
    if reporter.is_blocked:
        await message.answer(t("blocked", reporter.language))
        return

    limit_msg = await rate_limit_exceeded(reporter)
    if limit_msg:
        await message.answer(limit_msg)
        return

    await state.clear()

    # При первом обращении сначала спрашиваем язык, дальше он запоминается
    if not reporter.language_chosen:
        await message.answer(t("choose_language", reporter.language),
                             reply_markup=language_kb())
        return

    await begin_flow(message, state, reporter.language)


async def begin_flow(message: Message, state: FSMContext, lang: str):
    await state.update_data(lang=lang)
    await state.set_state(Flow.waiting_location)
    await message.answer(t("intro", lang), reply_markup=location_kb(lang))


@dp.message(Command("lang"))
async def cmd_lang(message: Message, state: FSMContext):
    reporter = await get_or_create_reporter(message.from_user)
    await message.answer(t("choose_language", reporter.language),
                         reply_markup=language_kb())


@dp.callback_query(F.data.startswith("lang:"))
async def pick_language(call: CallbackQuery, state: FSMContext):
    lang = call.data.split(":")[1]
    reporter = await get_or_create_reporter(call.from_user)
    await set_language(reporter, lang)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    await call.message.answer(t("language_set", lang))
    await begin_flow(call.message, state, lang)


async def state_lang(state: FSMContext) -> str:
    """Язык текущего диалога. Хранится в состоянии, а не в глобальной
    переменной, — иначе одновременные диалоги перебивали бы друг друга."""
    return (await state.get_data()).get("lang", "ru")


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    lang = await state_lang(state)
    await state.clear()
    await message.answer(t("cancelled", lang), reply_markup=ReplyKeyboardRemove())


@dp.message(Command("my"))
async def cmd_my(message: Message):
    reporter = await get_or_create_reporter(message.from_user)
    total = await count_user_reports(reporter)
    await message.answer(t("my_reports", reporter.language, count=total))


@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    reporter = await get_or_create_reporter(message.from_user)
    await message.answer(t("delete_info", reporter.language))


@dp.message(Flow.waiting_location, F.location)
async def got_location(message: Message, state: FSMContext):
    await state.update_data(lat=message.location.latitude, lng=message.location.longitude)
    await state.set_state(Flow.waiting_photo)
    await message.answer(t("ask_photo", await state_lang(state)),
                         reply_markup=ReplyKeyboardRemove())


@dp.message(Flow.waiting_location)
async def need_location(message: Message, state: FSMContext):
    lang = await state_lang(state)
    await message.answer(t("need_location", lang), reply_markup=location_kb(lang))


@dp.message(Flow.waiting_photo, F.photo)
async def got_photo(message: Message, state: FSMContext, bot: Bot):
    lang = await state_lang(state)
    photo = message.photo[-1]  # максимальное доступное разрешение
    if photo.file_size and photo.file_size > MAX_PHOTO_BYTES:
        await message.answer(t("photo_too_big", lang))
        return

    await message.answer(t("uploading", lang))
    buffer = await bot.download(photo.file_id)
    try:
        ref, storage_name = await save_photo(buffer.read())
    except OSError:
        await message.answer(t("photo_broken", lang))
        return

    await state.update_data(photo_ref=ref, storage=storage_name, message_id=message.message_id)
    await state.set_state(Flow.waiting_category)

    categories = await active_categories()
    await message.answer(t("ask_category", lang),
                         reply_markup=categories_kb(categories, lang))


@dp.message(Flow.waiting_photo, F.document)
async def photo_as_document(message: Message, state: FSMContext):
    await message.answer(t("photo_as_document", await state_lang(state)))


@dp.message(Flow.waiting_photo)
async def need_photo(message: Message, state: FSMContext):
    await message.answer(t("need_photo", await state_lang(state)))


@dp.callback_query(Flow.waiting_category, F.data.startswith("cat:"))
async def got_category(call: CallbackQuery, state: FSMContext):
    await state.update_data(category_id=int(call.data.split(":")[1]))
    await state.set_state(Flow.waiting_description)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    lang = await state_lang(state)
    await call.message.answer(t("ask_description", lang), reply_markup=skip_kb(lang))


async def _finish(target_message, state, from_user, description):
    data = await state.get_data()
    reporter = await get_or_create_reporter(from_user)
    report_id = await create_report(
        reporter, data["category_id"], data["lat"], data["lng"],
        data["photo_ref"], data["storage"], description, data.get("message_id"),
    )
    lang = data.get("lang", "ru")
    await state.clear()
    await target_message.answer(t("accepted", lang, id=report_id))


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
    reporter = await get_or_create_reporter(message.from_user)
    await message.answer(t("fallback", reporter.language))


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
