> Serverga joylash va bir buyruq bilan o'rnatish: **DEPLOY.md**

# Telegram ish bot (Django admin + aiogram)

## Ishga tushirish (3 qadam)

1. Kutubxonalarni o'rnatish:
       python -m venv venv
       source venv/bin/activate        (Windows: venv\Scripts\activate)
       pip install -r requirements.txt

2. `.env.example` faylini `.env` deb nomlang va `BOT_TOKEN=` ga tokenni qo'ying.

3. Bazani tayyorlang va admin yarating:
       python manage.py migrate
       python manage.py seed             (namuna ma'lumotlar, ixtiyoriy)
       python manage.py createsuperuser

Keyin ikkita terminalda:

       python manage.py runserver        -> admin panel: http://127.0.0.1:8000/
       python manage.py runbot           -> telegram bot

## Serverga joylash (deploy)
`.env` da: `DEBUG=False`, uzun tasodifiy `SECRET_KEY`, `ALLOWED_HOSTS=domen.uz`,
HTTPS bo'lsa `CSRF_TRUSTED_ORIGINS=https://domen.uz` va `USE_HTTPS=True` (namuna: `.env.example`).

       pip install -r requirements.txt
       python manage.py migrate
       python manage.py collectstatic --noinput
       gunicorn config.wsgi:application --bind 0.0.0.0:8000   -> admin panel
       python manage.py runbot                                 -> telegram bot (alohida jarayon)

Ikkala jarayonni systemd/supervisor orqali doimiy ishlating.

## Admin paneldan boshqariladi
- **Vakansiyalar** – qo'shish/o'chirish/yoqib-o'chirish (uz va ru tilda). Botda "Bo'sh ish o'rinlari" ostida chiqadi.
- **Bo'limlar (tugmalar)** – "Kompaniya haqida", "Aloqa" kabi istalgancha yangi tugma qo'shish mumkin.
  Bo'lim ichiga rasm/fayl va ichki tugmalar (har birining o'z matni va fayli bilan) qo'shiladi.
- **Xabarlar (shaxsiy yozishma)** – foydalanuvchiga lichkasiga xabar (matn, rasm, fayl) yuborish:
  foydalanuvchi sahifasining pastida, arizadagi "✉️ Xabar yozish" tugmasi orqali yoki ro'yxatda
  belgilab "✉️ Tanlanganlarga shaxsiy xabar yuborish" amali bilan. Foydalanuvchi botga yozgan
  oddiy matnlar ham shu yerda ko'rinadi. Yuklangan fayllar `media/` papkasida saqlanadi.
- **Arizalar** – foydalanuvchilar topshirgan arizalar (ism, telefon, vakansiya). Holatini o'zgartirish va CSV yuklash mumkin.
- **Bot matnlari** – botdagi barcha tugma va xabar matnlari (uz/ru).
- **Foydalanuvchilar** – botga kirganlar ro'yxati.

Yangi ariza haqida Telegramga xabar kelishi uchun `.env` da `ADMIN_CHAT_ID` ni yozing.
Barcha matnlar oddiy matn sifatida yoziladi (HTML kerak emas) – qatorlar va emojilar botda o'z holicha chiqadi.

## Qo'shimcha savollar (ariza uchun)
Vakansiyani ochganda pastda "Shu vakansiya uchun qo'shimcha savollar" bo'limi bor – u yerda savollar qo'shing
(matn, raqam, telefon yoki tugmali tanlov). "Savollar" bo'limida vakansiyasiz savol qo'shsangiz, u barcha
vakansiyalarda so'raladi. Javoblar "Arizalar" ichida har bir ariza ostida ko'rinadi.
Yangilashda: `python manage.py migrate` ni bajaring.
