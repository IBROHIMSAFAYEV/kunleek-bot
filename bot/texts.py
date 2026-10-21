"""Botdagi barcha standart matnlar. Admin paneldagi "Bot matnlari" bo'limidan o'zgartirish mumkin."""

LANGS = ("uz", "ru")

DEFAULTS = {
    "choose_language": {
        "uz": "🌐 Tilni tanlang / Выберите язык",
        "ru": "🌐 Tilni tanlang / Выберите язык",
    },
    "welcome": {
        "uz": "Assalomu alaykum! 👋\nBizning ish bo'yicha botimizga xush kelibsiz. Quyidagi bo'limlardan birini tanlang.",
        "ru": "Здравствуйте! 👋\nДобро пожаловать в наш бот по трудоустройству. Выберите один из разделов ниже.",
    },
    "main_menu": {"uz": "📋 Asosiy menyu", "ru": "📋 Главное меню"},
    "menu_vacancies": {"uz": "💼 Bo'sh ish o'rinlari", "ru": "💼 Вакансии"},
    "menu_language": {"uz": "🌐 Tilni o'zgartirish", "ru": "🌐 Сменить язык"},
    "language_changed": {"uz": "✅ Til o'zgartirildi", "ru": "✅ Язык изменён"},
    "vacancies_title": {
        "uz": "💼 Bo'sh ish o'rinlari ro'yxati. Kerakli vakansiyani tanlang:",
        "ru": "💼 Список вакансий. Выберите нужную:",
    },
    "no_vacancies": {
        "uz": "Hozircha bo'sh ish o'rinlari yo'q.",
        "ru": "Пока нет открытых вакансий.",
    },
    "address_label": {"uz": "Manzil", "ru": "Адрес"},
    "location_label": {"uz": "Joy", "ru": "Филиал"},
    "choose_location": {
        "uz": "📍 Qaysi joyda ishlamoqchisiz? Joyni tanlang:",
        "ru": "📍 Где вы хотите работать? Выберите филиал:",
    },
    "all_locations": {"uz": "🌐 Barcha joylar", "ru": "🌐 Все филиалы"},
    "apply_btn": {"uz": "✍️ Ariza topshirish", "ru": "✍️ Подать заявку"},
    "back_btn": {"uz": "⬅️ Orqaga", "ru": "⬅️ Назад"},
    "ask_name": {
        "uz": "Ism va familiyangizni kiriting:",
        "ru": "Введите ваше имя и фамилию:",
    },
    "ask_phone": {
        "uz": "Telefon raqamingizni yuboring (tugmani bosing yoki +998901234567 ko'rinishida yozing):",
        "ru": "Отправьте номер телефона (нажмите кнопку или введите в формате +998901234567):",
    },
    "send_phone_btn": {"uz": "📱 Raqamni yuborish", "ru": "📱 Отправить номер"},
    "invalid_phone": {
        "uz": "❗ Telefon raqami noto'g'ri. Qaytadan kiriting.",
        "ru": "❗ Неверный номер телефона. Попробуйте ещё раз.",
    },
    "applied": {
        "uz": "✅ Arizangiz qabul qilindi! Tez orada siz bilan bog'lanamiz.",
        "ru": "✅ Ваша заявка принята! Мы скоро свяжемся с вами.",
    },
    "message_received": {
        "uz": "✅ Xabaringiz yuborildi. Tez orada javob beramiz.",
        "ru": "✅ Ваше сообщение отправлено. Скоро ответим.",
    },
    "cancel_btn": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена"},
    "cancelled": {"uz": "Bekor qilindi.", "ru": "Отменено."},
    "skip_btn": {"uz": "⏭ O'tkazib yuborish", "ru": "⏭ Пропустить"},
    "invalid_number": {
        "uz": "❗ Iltimos, faqat raqam kiriting.",
        "ru": "❗ Пожалуйста, введите только число.",
    },
    "invalid_file": {
        "uz": "❗ Iltimos, faylni (PDF, Word) yoki rasmni yuboring.",
        "ru": "❗ Пожалуйста, отправьте файл (PDF, Word) или фото.",
    },
    "file_too_big": {
        "uz": "❗ Fayl juda katta (20 MB dan oshmasin). Kichikroq fayl yuboring.",
        "ru": "❗ Файл слишком большой (не более 20 МБ). Отправьте файл поменьше.",
    },
    "invalid_choice": {
        "uz": "❗ Iltimos, tugmalardan birini tanlang.",
        "ru": "❗ Пожалуйста, выберите один из вариантов.",
    },
}
