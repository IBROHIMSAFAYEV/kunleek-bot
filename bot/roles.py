"""Tayyor rollar (guruhlar) va standart xabar shablonlari. Faqat yo'q bo'lsa yaratiladi — admin o'zgartirganlariga tegilmaydi."""

BOT_MODELS = [
    "application", "answer", "directmessage", "telegramuser", "vacancy", "question", "section", "sectionitem",
    "bottext", "botprofile", "announcement", "messagetemplate", "location",
]
# keyin qo'shilgan modellar: mavjud rollar ham shu modelga o'xshash ruxsat oladi (vakansiyadagidek)
MIRROR = {"location": "vacancy"}

ROLES = {
    "HR menejer": {
        "view": BOT_MODELS,
        "add": ["directmessage", "vacancy", "question", "announcement", "messagetemplate"],
        "change": ["application", "telegramuser", "vacancy", "question", "announcement", "messagetemplate"],
        "extra": ["send_announcement"],
    },
    "HR yordamchi (yozishma)": {
        "view": ["application", "answer", "directmessage", "telegramuser", "vacancy", "messagetemplate"],
        "add": ["directmessage"],
        "change": ["application"],
        "extra": [],
    },
    "Kontent menejer": {
        "view": BOT_MODELS,
        "add": ["vacancy", "question", "section", "sectionitem", "announcement", "messagetemplate"],
        "change": ["vacancy", "question", "section", "sectionitem", "bottext", "botprofile", "announcement", "messagetemplate"],
        "delete": ["vacancy", "question", "section", "sectionitem", "announcement", "messagetemplate"],
        "extra": ["send_announcement"],
    },
    "Faqat ko'rish": {"view": BOT_MODELS, "extra": []},
}

TEMPLATES = [
    ("status_accepted", "Qabul qilindi", 0,
     "Assalomu alaykum, {ism}! 🎉\n\nTabriklaymiz! Siz \"{vakansiya}\" lavozimiga qabul qilindingiz. "
     "Tez orada siz bilan bog'lanib, keyingi qadamlarni aytamiz.",
     "Здравствуйте, {ism}! 🎉\n\nПоздравляем! Вы приняты на должность «{vakansiya}». "
     "Мы скоро свяжемся с вами и расскажем о следующих шагах."),
    ("status_rejected", "Rad etildi", 0,
     "Assalomu alaykum, {ism}.\n\n\"{vakansiya}\" lavozimiga qiziqish bildirganingiz uchun rahmat. "
     "Afsuski, hozircha boshqa nomzodni tanladik. Arizangizni saqlab qo'yamiz va mos vakansiya chiqsa, albatta xabar beramiz.",
     "Здравствуйте, {ism}.\n\nСпасибо за интерес к должности «{vakansiya}». "
     "К сожалению, сейчас мы выбрали другого кандидата. Мы сохраним вашу заявку и сообщим, если появится подходящая вакансия."),
    ("interview_invite", "Suhbatga taklif", 0,
     "Assalomu alaykum, {ism}!\n\nSizni \"{vakansiya}\" lavozimi bo'yicha suhbatga taklif qilamiz.\n\n"
     "📅 Sana: {sana}\n🕐 Vaqt: {vaqt}\n📍 Manzil: {manzil}\n\nKela olmasangiz, shu yerga yozib qoldiring.",
     "Здравствуйте, {ism}!\n\nПриглашаем вас на собеседование на должность «{vakansiya}».\n\n"
     "📅 Дата: {sana}\n🕐 Время: {vaqt}\n📍 Адрес: {manzil}\n\nЕсли не сможете прийти, напишите сюда."),
    ("interview_reminder", "Suhbat eslatmasi", 0,
     "⏰ Eslatma, {ism}: {sana} kuni soat {vaqt} da suhbatingiz bor.\n📍 {manzil}\n\nSizni kutamiz!",
     "⏰ Напоминание, {ism}: {sana} в {vaqt} у вас собеседование.\n📍 {manzil}\n\nЖдём вас!"),
    ("quick", "Suhbatga taklif", 1,
     "Assalomu alaykum, {ism}! Arizangizni ko'rib chiqdik. Suhbatga qachon kela olasiz?",
     "Здравствуйте, {ism}! Мы рассмотрели вашу заявку. Когда вам удобно прийти на собеседование?"),
    ("quick", "Manzil", 2,
     "📍 Manzilimiz: {manzil}\n🕐 Ish vaqti: 10:00–18:00",
     "📍 Наш адрес: {manzil}\n🕐 Время работы: 10:00–18:00"),
    ("quick", "Hujjatlar ro'yxati", 3,
     "Suhbatga quyidagi hujjatlarni olib keling:\n• Pasport (nusxasi)\n• Diplom yoki attestat\n• 3x4 rasm (2 dona)",
     "Возьмите на собеседование:\n• Паспорт (копию)\n• Диплом или аттестат\n• Фото 3x4 (2 шт.)"),
    ("quick", "Rahmat", 4,
     "Rahmat, {ism}! Ma'lumotni oldik, tez orada javob beramiz.",
     "Спасибо, {ism}! Информацию получили, скоро ответим."),
]


def ensure_roles_and_templates(**kwargs):
    from django.contrib.auth.models import Group, Permission

    from .models import MessageTemplate

    # mavjud rollarga yangi modellar uchun ruxsat: masalan vakansiyani ko'ra olgan — joyni ham ko'ra oladi
    for group in Group.objects.prefetch_related("permissions"):
        have = {p.codename for p in group.permissions.all()}
        for new, like in MIRROR.items():
            add = [f"{act}_{new}" for act in ("view", "add", "change", "delete") if f"{act}_{like}" in have and f"{act}_{new}" not in have]
            if add:
                group.permissions.add(*Permission.objects.filter(content_type__app_label="bot", codename__in=add))

    for name, spec in ROLES.items():
        group, created = Group.objects.get_or_create(name=name)
        if not created:
            continue
        codenames = [f"{act}_{model}" for act in ("view", "add", "change", "delete") for model in spec.get(act, [])]
        codenames += spec.get("extra", [])
        group.permissions.set(Permission.objects.filter(content_type__app_label="bot", codename__in=codenames))

    if not MessageTemplate.objects.exists():
        MessageTemplate.objects.bulk_create([
            MessageTemplate(kind=k, title=t, order=o, text_uz=uz, text_ru=ru) for k, t, o, uz, ru in TEMPLATES
        ])
