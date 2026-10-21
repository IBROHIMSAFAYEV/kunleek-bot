import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bot.models import ensure_texts
from bot.telegram import set_webhook


class Command(BaseCommand):
    help = "Botni webhook rejimiga o'tkazadi: python manage.py setwebhook https://sayt.uz"

    def add_arguments(self, parser):
        parser.add_argument("site_url", help="Saytning to'liq manzili, masalan https://ism.pythonanywhere.com")

    def handle(self, site_url, **options):
        if not settings.BOT_TOKEN or not settings.WEBHOOK_SECRET:
            raise CommandError("BOT_TOKEN va WEBHOOK_SECRET .env faylda bo'lishi kerak")
        ensure_texts()
        info = asyncio.run(set_webhook(site_url.rstrip("/") + "/tg/webhook/"))
        self.stdout.write(self.style.SUCCESS(f"Webhook o'rnatildi: {info.url}"))
        if info.last_error_message:
            self.stdout.write(f"Oxirgi xato: {info.last_error_message}")
