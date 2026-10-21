import os

from django.conf import settings
from django.db import models

from .texts import DEFAULTS


def file_path(f):
    """Yuklangan fayl diskda bo'lsa, uning yo'lini qaytaradi."""
    return f.path if f and os.path.exists(f.path) else None


class TelegramUser(models.Model):
    LANG_CHOICES = [("uz", "O'zbekcha"), ("ru", "Русский")]

    tg_id = models.BigIntegerField("Telegram ID", unique=True)
    full_name = models.CharField("Ism", max_length=255, blank=True)
    username = models.CharField("Username", max_length=255, blank=True)
    language = models.CharField("Til", max_length=2, choices=LANG_CHOICES, blank=True)
    phone = models.CharField("Telefon", max_length=50, blank=True, help_text="Ariza topshirganda yuborgan raqami")
    created_at = models.DateTimeField("Qo'shilgan vaqt", auto_now_add=True)

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name or str(self.tg_id)


class Section(models.Model):
    """Botdagi qo'shimcha bo'limlar (Kompaniya haqida, Aloqa va h.k.). Har biri menyuda tugma bo'lib chiqadi."""

    title_uz = models.CharField("Tugma nomi (uz)", max_length=100)
    title_ru = models.CharField("Tugma nomi (ru)", max_length=100)
    content_uz = models.TextField("Matn (uz)", blank=True, help_text="Oddiy matn yozing. Qatorlar va emojilar botda o'z holicha chiqadi.")
    content_ru = models.TextField("Matn (ru)", blank=True, help_text="Bo'sh qolsa, o'zbekcha matn chiqadi.")
    file = models.FileField("Rasm yoki fayl", upload_to="sections/", blank=True)
    order = models.PositiveIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Bo'lim (tugma)"
        verbose_name_plural = "Bo'limlar (tugmalar)"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title_uz

    def title(self, lang):
        return self.title_ru if lang == "ru" else self.title_uz

    def content(self, lang):
        return (self.content_ru if lang == "ru" else "") or self.content_uz


class SectionItem(models.Model):
    """Bo'lim ichidagi tugmalar: bo'lim ochilganda uning ostida chiqadi."""

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="items", verbose_name="Bo'lim")
    title_uz = models.CharField("Tugma nomi (uz)", max_length=100)
    title_ru = models.CharField("Tugma nomi (ru)", max_length=100, blank=True, help_text="Bo'sh qolsa, o'zbekcha nom chiqadi.")
    content_uz = models.TextField("Matn (uz)", blank=True, help_text="Oddiy matn yozing.")
    content_ru = models.TextField("Matn (ru)", blank=True, help_text="Bo'sh qolsa, o'zbekcha matn chiqadi.")
    file = models.FileField("Rasm yoki fayl", upload_to="sections/", blank=True)
    order = models.PositiveIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Ichki tugma"
        verbose_name_plural = "Bo'lim ichidagi tugmalar"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title_uz

    def title(self, lang):
        return (self.title_ru if lang == "ru" else "") or self.title_uz

    def content(self, lang):
        return (self.content_ru if lang == "ru" else "") or self.content_uz


class Location(models.Model):
    """Joy / filial: botda avval joy tanlanadi, so'ng shu joyning vakansiyalari chiqadi."""

    name_uz = models.CharField("Nomi (uz)", max_length=120, help_text="Masalan: Chilonzor filiali")
    name_ru = models.CharField("Nomi (ru)", max_length=120, blank=True, help_text="Bo'sh qolsa, o'zbekchasi ko'rinadi.")
    address = models.CharField("Manzil", max_length=255, blank=True, help_text="Masalan: Toshkent, Chilonzor 5-kvartal, 12-uy")
    map_url = models.URLField("Xaritadagi havola", blank=True, help_text="Google/Yandex xarita havolasi (ixtiyoriy)")
    order = models.PositiveIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Joy (filial)"
        verbose_name_plural = "Joylar (filiallar)"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name_uz

    def name(self, lang):
        return (self.name_ru if lang == "ru" else "") or self.name_uz


class Vacancy(models.Model):
    title_uz = models.CharField("Nomi (uz)", max_length=200)
    title_ru = models.CharField("Nomi (ru)", max_length=200)
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="vacancies", verbose_name="Joy (filial)",
        help_text="Botda nomzod shu joyni tanlaganda vakansiya chiqadi.",
    )
    description_uz = models.TextField("Tavsif (uz)", blank=True)
    description_ru = models.TextField("Tavsif (ru)", blank=True)
    address = models.CharField("Manzil", max_length=255, blank=True, help_text="Bo'sh qolsa, joyning manzili ko'rsatiladi.")
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "Vakansiya"
        verbose_name_plural = "Vakansiyalar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title_uz

    def title(self, lang):
        return self.title_ru if lang == "ru" else self.title_uz

    def description(self, lang):
        return self.description_ru if lang == "ru" else self.description_uz

    def full_address(self):
        return self.address or (self.location.address if self.location else "")


class Application(models.Model):
    STATUS = [
        ("new", "Yangi"),
        ("viewed", "Ko'rildi"),
        ("interview", "Suhbatga chaqirildi"),
        ("accepted", "Qabul qilindi"),
        ("rejected", "Rad etildi"),
    ]

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="applications", verbose_name="Foydalanuvchi")
    vacancy = models.ForeignKey(Vacancy, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vakansiya")
    vacancy_title = models.CharField("Vakansiya nomi", max_length=200, blank=True)
    full_name = models.CharField("F.I.Sh.", max_length=255)
    phone = models.CharField("Telefon", max_length=50)
    status = models.CharField(
        "Holat", max_length=10, choices=STATUS, default="new",
        help_text="\"Qabul qilindi\" yoki \"Rad etildi\" qilinsa, nomzodga shablon bo'yicha xabar o'zi boradi.",
    )
    interview_at = models.DateTimeField(
        "Suhbat vaqti", null=True, blank=True,
        help_text="Belgilansa, nomzodga taklif boradi; suhbatdan 24 soat oldin eslatma yuboriladi.",
    )
    interview_place = models.CharField(
        "Suhbat manzili", max_length=255, blank=True, help_text="Bo'sh qolsa, vakansiya manzili ishlatiladi.",
    )
    reminder_sent = models.BooleanField("Eslatma yuborilgan", default=False)
    created_at = models.DateTimeField("Vaqt", auto_now_add=True)

    class Meta:
        verbose_name = "Ariza"
        verbose_name_plural = "Arizalar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.vacancy_title}"


class Question(models.Model):
    """Ariza topshirishda foydalanuvchidan so'raladigan qo'shimcha savollar."""

    TYPES = [
        ("text", "Oddiy matn"),
        ("number", "Raqam"),
        ("phone", "Telefon raqam"),
        ("choice", "Tanlov (tugmalar)"),
        ("file", "Fayl yoki rasm (rezyume)"),
    ]

    vacancy = models.ForeignKey(
        Vacancy, on_delete=models.CASCADE, null=True, blank=True, related_name="questions",
        verbose_name="Vakansiya", help_text="Bo'sh qoldirsangiz, savol BARCHA vakansiyalarda so'raladi",
    )
    text_uz = models.CharField("Savol (uz)", max_length=300)
    text_ru = models.CharField("Savol (ru)", max_length=300)
    answer_type = models.CharField("Javob turi", max_length=10, choices=TYPES, default="text")
    options_uz = models.TextField("Variantlar (uz)", blank=True, help_text="Faqat 'Tanlov' turi uchun. Har qatorga bitta variant.")
    options_ru = models.TextField("Variantlar (ru)", blank=True)
    is_required = models.BooleanField("Majburiy", default=True)
    order = models.PositiveIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ["order", "id"]

    def __str__(self):
        return self.text_uz

    def text(self, lang):
        return self.text_ru if lang == "ru" else self.text_uz

    def options(self, lang):
        raw = self.options_ru if lang == "ru" else self.options_uz
        return [o.strip() for o in raw.splitlines() if o.strip()]


class Answer(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="answers")
    question_text = models.CharField("Savol", max_length=300)
    answer = models.TextField("Javob")
    file = models.FileField("Fayl", upload_to="answers/", blank=True)

    class Meta:
        verbose_name = "Javob"
        verbose_name_plural = "Javoblar"
        ordering = ["id"]

    def __str__(self):
        return f"{self.question_text}: {self.answer}"


class BotText(models.Model):
    key = models.CharField("Kalit", max_length=50, unique=True)
    value_uz = models.TextField("Matn (uz)")
    value_ru = models.TextField("Matn (ru)")

    class Meta:
        verbose_name = "Bot matni"
        verbose_name_plural = "Bot matnlari"
        ordering = ["key"]

    def __str__(self):
        return self.key

    def value(self, lang):
        return self.value_ru if lang == "ru" else self.value_uz


class DirectMessage(models.Model):
    """Admin va foydalanuvchi o'rtasidagi shaxsiy yozishma."""

    DIRECTIONS = [("out", "Admin → foydalanuvchi"), ("in", "Foydalanuvchi → admin")]
    STATUS = [
        ("pending", "Yuborilmoqda"),
        ("sent", "Yuborildi"),
        ("error", "Yuborilmadi"),
        ("received", "Qabul qilindi"),
    ]

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="messages", verbose_name="Foydalanuvchi")
    application = models.ForeignKey(
        Application, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages", verbose_name="Ariza",
    )
    direction = models.CharField("Yo'nalish", max_length=3, choices=DIRECTIONS, default="out")
    text = models.TextField("Matn", blank=True)
    file = models.FileField("Rasm yoki fayl", upload_to="messages/", blank=True)
    status = models.CharField("Holat", max_length=10, choices=STATUS, default="pending")
    error = models.TextField("Xato", blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_messages",
        verbose_name="Kim yozdi",
    )
    is_auto = models.BooleanField("Avtomatik", default=False, help_text="Shablon bo'yicha bot o'zi yuborgan")
    created_at = models.DateTimeField("Vaqt", auto_now_add=True)

    class Meta:
        verbose_name = "Xabar"
        verbose_name_plural = "Xabarlar (shaxsiy yozishma)"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} — {self.text[:40]}"


class Announcement(models.Model):
    """Botga /start bosgan barcha foydalanuvchilarga yuboriladigan e'lon."""

    AUDIENCE = [("all", "Hammaga"), ("uz", "Faqat o'zbek tilidagilarga"), ("ru", "Faqat rus tilidagilarga")]
    STATUS = [("draft", "Qoralama"), ("sent", "Yuborilgan")]

    text_uz = models.TextField("Matn (uz)", help_text="Oddiy matn. Qatorlar va emojilar botda o'z holicha chiqadi.")
    text_ru = models.TextField("Matn (ru)", blank=True, help_text="Bo'sh qolsa, ruschani tanlaganlarga o'zbekcha matn boradi.")
    file = models.FileField("Rasm yoki fayl", upload_to="announcements/", blank=True)
    audience = models.CharField("Kimga", max_length=3, choices=AUDIENCE, default="all")
    status = models.CharField("Holat", max_length=10, choices=STATUS, default="draft")
    sent_count = models.PositiveIntegerField("Yetkazildi", default=0)
    failed_count = models.PositiveIntegerField("Yetmadi", default=0)
    sent_at = models.DateTimeField("Yuborilgan vaqt", null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="Kim yubordi",
    )
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "E'lon"
        verbose_name_plural = "E'lonlar"
        ordering = ["-created_at"]
        permissions = [("send_announcement", "E'lonni hammaga yuborish")]

    def __str__(self):
        return self.text_uz[:60]

    def text(self, lang):
        return (self.text_ru if lang == "ru" else "") or self.text_uz

    def recipients(self):
        users = TelegramUser.objects.all()
        if self.audience == "uz":
            users = users.exclude(language="ru")  # tilni tanlamaganlar ham o'zbekcha oladi
        elif self.audience == "ru":
            users = users.filter(language="ru")
        return users


class MessageTemplate(models.Model):
    """Nomzodlarga yuboriladigan tayyor xabarlar: avtomatik (holat, suhbat) va tezkor javoblar."""

    KINDS = [
        ("quick", "Tezkor javob — yozishmada tugma"),
        ("status_accepted", "Avtomatik: holat \"Qabul qilindi\""),
        ("status_rejected", "Avtomatik: holat \"Rad etildi\""),
        ("interview_invite", "Avtomatik: suhbatga taklif"),
        ("interview_reminder", "Avtomatik: suhbat eslatmasi (24 soat oldin)"),
    ]
    PLACEHOLDERS = "{ism} — nomzod ismi, {vakansiya}, {sana}, {vaqt} — suhbat sanasi/vaqti, {manzil}"

    kind = models.CharField("Turi", max_length=20, choices=KINDS, default="quick")
    title = models.CharField("Nomi", max_length=60, help_text="Tezkor javob tugmasida shu yoziladi.")
    text_uz = models.TextField("Matn (uz)", help_text="Qo'yish mumkin: " + PLACEHOLDERS)
    text_ru = models.TextField("Matn (ru)", blank=True, help_text="Bo'sh qolsa, o'zbekcha matn ishlatiladi.")
    is_active = models.BooleanField("Faol", default=True, help_text="O'chirilsa, avtomatik xabar yuborilmaydi.")
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Xabar shabloni"
        verbose_name_plural = "Xabar shablonlari"
        ordering = ["kind", "order", "id"]

    def __str__(self):
        return self.title

    def render(self, app, lang):
        """Shablondagi {ism}, {vakansiya}... larni arizadagi qiymatlar bilan almashtiradi."""
        from django.utils.timezone import localtime

        text = (self.text_ru if lang == "ru" else "") or self.text_uz
        when = localtime(app.interview_at) if app and app.interview_at else None
        place = (app.interview_place or (app.vacancy.full_address() if app.vacancy else "")) if app else ""
        values = {
            "{ism}": app.full_name if app else "",
            "{vakansiya}": (app.vacancy.title(lang) if app and app.vacancy else (app.vacancy_title if app else "")),
            "{sana}": when.strftime("%d.%m.%Y") if when else "",
            "{vaqt}": when.strftime("%H:%M") if when else "",
            "{manzil}": place,
        }
        for key, value in values.items():
            text = text.replace(key, value)
        return text


class BotProfile(models.Model):
    """Telegramdagi bot profili: nom, avatar, tavsiflar. Saqlanganda Telegramga yuboriladi (yagona yozuv)."""

    name_uz = models.CharField("Bot nomi (uz)", max_length=64)
    name_ru = models.CharField("Bot nomi (ru)", max_length=64, blank=True, help_text="Bo'sh qolsa, o'zbekchasi ko'rinadi.")
    short_description_uz = models.CharField(
        "Profildagi qisqa tavsif (uz)", max_length=120, blank=True,
        help_text="Bot profilida nom ostida chiqadi (\"About\"). 120 belgigacha.",
    )
    short_description_ru = models.CharField("Profildagi qisqa tavsif (ru)", max_length=120, blank=True)
    description_uz = models.TextField(
        "Bot haqida — start oldidan (uz)", max_length=512, blank=True,
        help_text="Foydalanuvchi botni birinchi ochganda, START tugmasidan oldin chiqadi. 512 belgigacha.",
    )
    description_ru = models.TextField("Bot haqida — start oldidan (ru)", max_length=512, blank=True)
    photo = models.ImageField(
        "Avatar (rasm)", upload_to="bot_profile/", blank=True,
        help_text="JPG yoki PNG. Kvadrat qilib kesiladi. Yangi rasm yuklasangiz, Telegramdagi avatar almashadi.",
    )
    photo_synced = models.CharField(max_length=255, blank=True, editable=False)
    synced_at = models.DateTimeField("Telegramga oxirgi yuborilgan", null=True, blank=True)
    last_error = models.TextField("Oxirgi xato", blank=True)

    class Meta:
        verbose_name = "Bot profili"
        verbose_name_plural = "Bot profili"

    def __str__(self):
        return self.name_uz


class FSMRecord(models.Model):
    """Bot suhbat holati (ariza bosqichi va h.k.) — webhook rejimida so'rovlar orasida saqlanishi uchun."""

    key = models.CharField(max_length=255, unique=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    data = models.JSONField(default=dict)


def ensure_texts():
    """Standart matnlarni bazaga yozadi (mavjudlariga tegmaydi)."""
    for key, v in DEFAULTS.items():
        BotText.objects.get_or_create(key=key, defaults={"value_uz": v["uz"], "value_ru": v["ru"]})
