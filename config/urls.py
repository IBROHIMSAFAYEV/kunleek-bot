from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path, re_path
from django.views.static import serve

from bot.views import telegram_webhook

urlpatterns = [
    path("tg/webhook/", telegram_webhook),
    # yuklangan rasm/fayllar faqat admin uchun ochiladi
    re_path(r"^media/(?P<path>.*)$", staff_member_required(serve), {"document_root": settings.MEDIA_ROOT}),
    path("", admin.site.urls),
]
