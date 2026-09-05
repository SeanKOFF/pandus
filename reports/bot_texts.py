"""Тексты бота на русском и узбекском.

Почему словарь, а не gettext: aiogram обрабатывает сообщения в одном
потоке асинхронно, а активный язык в Django — потоко-локальный. При
одновременных диалогах на разных языках он «протёк» бы между
пользователями. Явная передача языка такой ошибки не допускает.
"""

TEXTS = {
    "choose_language": {
        "ru": "Выберите язык / Tilni tanlang",
        "uz": "Выберите язык / Tilni tanlang",
    },
    "language_set": {
        "ru": "Язык переключён на русский.",
        "uz": "Til o‘zbekchaga o‘zgartirildi.",
    },
    "intro": {
        "ru": (
            "Здесь можно сообщить о месте, где нет условий для проезда: "
            "отсутствует пандус, разбит тротуар, перекрыт проход.\n\n"
            "Что важно знать: присланные фотографии и координаты места "
            "публикуются на открытой карте города — их увидит любой человек. "
            "Ваше имя и контакты не публикуются. Если позже захотите убрать "
            "свою заявку с карты, напишите /delete.\n\n"
            "Отправляя заявку, вы соглашаетесь с публикацией фотографии.\n\n"
            "Шаг 1 из 3. Отправьте геолокацию места — кнопкой ниже "
            "или через скрепку → «Геопозиция»."
        ),
        "uz": (
            "Bu yerda harakatlanish uchun sharoit yo‘q joylar haqida xabar "
            "berishingiz mumkin: pandus yo‘q, piyodalar yo‘lkasi buzilgan, "
            "o‘tish joyi to‘silgan.\n\n"
            "Muhim: yuborilgan suratlar va joy koordinatalari shahar ochiq "
            "xaritasida e’lon qilinadi — ularni har kim ko‘radi. Ismingiz va "
            "aloqa ma’lumotlaringiz e’lon qilinmaydi. Keyinchalik arizangizni "
            "xaritadan olib tashlamoqchi bo‘lsangiz, /delete deb yozing.\n\n"
            "Ariza yuborish orqali siz suratning e’lon qilinishiga rozilik "
            "bildirasiz.\n\n"
            "1-qadam (3 tadan). Joyning geolokatsiyasini yuboring — quyidagi "
            "tugma orqali yoki qisqich → «Geopozitsiya»."
        ),
    },
    "send_location_btn": {
        "ru": "📍 Отправить геолокацию",
        "uz": "📍 Geolokatsiyani yuborish",
    },
    "need_location": {
        "ru": ("Нужна геолокация места. Нажмите кнопку ниже или отправьте "
               "точку через скрепку → «Геопозиция»."),
        "uz": ("Joyning geolokatsiyasi kerak. Quyidagi tugmani bosing yoki "
               "qisqich → «Geopozitsiya» orqali yuboring."),
    },
    "ask_photo": {
        "ru": ("Шаг 2 из 3. Теперь пришлите фотографию места.\n\n"
               "Снимайте так, чтобы в кадр не попадали лица людей, "
               "номера автомобилей и таблички с адресами квартир — "
               "фотография будет опубликована открыто."),
        "uz": ("2-qadam (3 tadan). Endi joyning suratini yuboring.\n\n"
               "Suratga odamlarning yuzlari, avtomobil raqamlari va kvartira "
               "manzillari tushmasligiga harakat qiling — surat ochiq "
               "e’lon qilinadi."),
    },
    "need_photo": {
        "ru": "Нужна фотография места. Пришлите снимок или отмените заявку: /cancel",
        "uz": "Joyning surati kerak. Surat yuboring yoki arizani bekor qiling: /cancel",
    },
    "photo_as_document": {
        "ru": ("Пришлите снимок именно как фото, а не файлом — "
               "так он корректно отобразится на карте."),
        "uz": ("Suratni fayl sifatida emas, rasm sifatida yuboring — "
               "shunda u xaritada to‘g‘ri ko‘rinadi."),
    },
    "photo_too_big": {
        "ru": "Файл слишком большой. Пришлите снимок поменьше.",
        "uz": "Fayl juda katta. Kichikroq surat yuboring.",
    },
    "photo_broken": {
        "ru": "Не удалось обработать изображение. Попробуйте прислать другой снимок.",
        "uz": "Suratni qayta ishlab bo‘lmadi. Boshqa surat yuborib ko‘ring.",
    },
    "uploading": {
        "ru": "Загружаю фото…",
        "uz": "Surat yuklanmoqda…",
    },
    "ask_category": {
        "ru": "Шаг 3 из 3. Выберите, в чём проблема:",
        "uz": "3-qadam (3 tadan). Muammo nimada ekanini tanlang:",
    },
    "ask_description": {
        "ru": ("Добавьте короткое описание — ориентир, адрес, детали. "
               "Или пропустите этот шаг."),
        "uz": ("Qisqacha izoh qo‘shing — mo‘ljal, manzil, tafsilotlar. "
               "Yoki bu qadamni o‘tkazib yuboring."),
    },
    "skip_btn": {
        "ru": "Пропустить",
        "uz": "O‘tkazib yuborish",
    },
    "accepted": {
        "ru": ("Заявка №{id} принята и отправлена на проверку.\n\n"
               "После одобрения модератором точка появится на карте города. "
               "Чтобы сообщить о другом месте — /start"),
        "uz": ("№{id} ariza qabul qilindi va tekshiruvga yuborildi.\n\n"
               "Moderator tasdiqlagach, nuqta shahar xaritasida paydo bo‘ladi. "
               "Boshqa joy haqida xabar berish uchun — /start"),
    },
    "cancelled": {
        "ru": "Заявка отменена. Чтобы начать заново — /start",
        "uz": "Ariza bekor qilindi. Qaytadan boshlash uchun — /start",
    },
    "my_reports": {
        "ru": "Вы отправили заявок: {count}",
        "uz": "Siz yuborgan arizalar soni: {count}",
    },
    "delete_info": {
        "ru": ("Чтобы убрать заявку с карты, пришлите её номер и короткое "
               "пояснение сюда: заявки снимает модератор вручную.\n\n"
               "Посмотреть свои заявки: /my"),
        "uz": ("Arizani xaritadan olib tashlash uchun uning raqamini va "
               "qisqacha izohni shu yerga yuboring: arizalarni moderator "
               "qo‘lda olib tashlaydi.\n\nArizalaringizni ko‘rish: /my"),
    },
    "blocked": {
        "ru": "Приём заявок с этого аккаунта приостановлен.",
        "uz": "Bu akkauntdan ariza qabul qilish to‘xtatilgan.",
    },
    "limit_hour": {
        "ru": "Вы отправили {n} заявок за последний час. Продолжить можно позже.",
        "uz": "Siz so‘nggi bir soatda {n} ta ariza yubordingiz. Keyinroq davom ettirishingiz mumkin.",
    },
    "limit_day": {
        "ru": "Вы отправили {n} заявок за сутки. Продолжить можно завтра.",
        "uz": "Siz bir kunda {n} ta ariza yubordingiz. Ertaga davom ettirishingiz mumkin.",
    },
    "fallback": {
        "ru": "Чтобы сообщить о проблемном месте, начните с команды /start",
        "uz": "Muammoli joy haqida xabar berish uchun /start buyrug‘idan boshlang",
    },
}


def t(key: str, lang: str = "ru", **kwargs) -> str:
    """Текст по ключу на нужном языке. Неизвестный язык — русский."""
    variants = TEXTS[key]
    text = variants.get(lang, variants["ru"])
    return text.format(**kwargs) if kwargs else text
