import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
# Baza va yuklangan fayllar shu papkada (serverda doimiy diskka ko'rsating, masalan /data)
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEBUG = os.getenv("DEBUG", "False").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key" if DEBUG else "")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY topilmadi. .env faylga uzun tasodifiy kalit yozing.")
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
# Railway domenini avtomatik qo'shamiz
if os.getenv("RAILWAY_PUBLIC_DOMAIN"):
    ALLOWED_HOSTS.append(os.environ["RAILWAY_PUBLIC_DOMAIN"])
    CSRF_TRUSTED_ORIGINS.append("https://" + os.environ["RAILWAY_PUBLIC_DOMAIN"])

# HTTPS orqali ishlaganda (serverda) xavfsiz cookie va yo'naltirish
USE_HTTPS = os.getenv("USE_HTTPS", "False").lower() == "true"
if USE_HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
# Webhook rejimi (PythonAnywhere): Telegram so'rovini tasdiqlovchi maxfiy kalit
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
# PythonAnywhere bepul tarifida: http://proxy.server:3128
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "")

INSTALLED_APPS = [
    "unfold",  # zamonaviy admin tema (django.contrib.admin dan oldin turishi shart)
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "bot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = DATA_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- admin panel dizayni (django-unfold)
from django.templatetags.static import static  # noqa: E402
from django.urls import reverse_lazy  # noqa: E402


def _nav(title, icon, url_name, badge=None):
    item = {"title": title, "icon": icon, "link": reverse_lazy(url_name)}
    if badge:
        item["badge"] = badge
    if url_name.endswith("_changelist"):  # ruxsati yo'q xodimga menyuda ko'rinmasin
        app, model = url_name.split(":")[1].removesuffix("_changelist").split("_", 1)
        item["permission"] = lambda request, perm=f"{app}.view_{model}": request.user.has_perm(perm)
    return item


UNFOLD = {
    "SITE_TITLE": "Kunleek HR",
    "SITE_HEADER": "Kunleek HR",
    "SITE_SUBHEADER": "Ish bot boshqaruvi",
    "SITE_SYMBOL": "work",
    "SITE_URL": None,
    "SHOW_HISTORY": True,  # kim nimani o'zgartirgani ko'rinadi
    "SHOW_VIEW_ON_SITE": False,
    "DASHBOARD_CALLBACK": "bot.dashboard.dashboard_callback",
    "STYLES": [lambda request: static("bot/admin.css")],
    "SCRIPTS": [lambda request: static("bot/admin.js")],
    "COLORS": {
        "primary": {
            "50": "oklch(98.2% .018 155.826)",
            "100": "oklch(96.2% .044 156.743)",
            "200": "oklch(92.5% .084 155.995)",
            "300": "oklch(87.1% .15 154.449)",
            "400": "oklch(79.2% .209 151.711)",
            "500": "oklch(72.3% .219 149.579)",
            "600": "oklch(62.7% .194 149.214)",
            "700": "oklch(52.7% .154 150.069)",
            "800": "oklch(44.8% .119 151.328)",
            "900": "oklch(39.3% .095 152.535)",
            "950": "oklch(26.6% .065 152.934)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "navigation": [
            {"title": "Asosiy", "items": [
                _nav("Bosh sahifa", "dashboard", "admin:index"),
                _nav("Arizalar", "assignment_ind", "admin:bot_application_changelist", "bot.dashboard.badge_new_applications"),
                _nav("Ariza javoblari", "fact_check", "admin:bot_answer_changelist"),
                _nav("Yozishmalar", "forum", "admin:bot_directmessage_changelist", "bot.dashboard.badge_unanswered"),
                _nav("E'lonlar", "campaign", "admin:bot_announcement_changelist"),
                _nav("Foydalanuvchilar", "group", "admin:bot_telegramuser_changelist"),
            ]},
            {"title": "Bot mazmuni", "items": [
                _nav("Bot profili", "smart_toy", "admin:bot_botprofile_changelist"),
                _nav("Joylar (filiallar)", "location_on", "admin:bot_location_changelist"),
                _nav("Vakansiyalar", "work", "admin:bot_vacancy_changelist"),
                _nav("Ariza savollari", "quiz", "admin:bot_question_changelist"),
                _nav("Bo'limlar (tugmalar)", "widgets", "admin:bot_section_changelist"),
                _nav("Xabar shablonlari", "quickreply", "admin:bot_messagetemplate_changelist"),
                _nav("Bot matnlari", "translate", "admin:bot_bottext_changelist"),
            ]},
            {"title": "Tizim", "items": [
                _nav("Xodimlar", "badge", "admin:auth_user_changelist"),
                _nav("Rollar va ruxsatlar", "admin_panel_settings", "admin:auth_group_changelist"),
            ]},
        ],
    },
}
