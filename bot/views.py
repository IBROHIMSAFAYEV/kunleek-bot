import asyncio
import json
import logging
from hmac import compare_digest

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .telegram import process_update

log = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    """Telegram yangilanishlarini qabul qiladi (webhook rejimi)."""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not settings.WEBHOOK_SECRET or not compare_digest(secret, settings.WEBHOOK_SECRET):
        return HttpResponseForbidden()
    try:
        asyncio.run(process_update(json.loads(request.body)))
    except Exception:  # noqa — Telegram qayta-qayta yubormasligi uchun baribir 200 qaytaramiz
        log.exception("Webhook yangilanishini qayta ishlashda xato")
    return HttpResponse("ok")
