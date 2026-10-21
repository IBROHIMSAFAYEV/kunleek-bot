from django.core.management.base import BaseCommand

from bot.telegram import run


class Command(BaseCommand):
    help = "Telegram botni ishga tushiradi"

    def handle(self, *args, **options):
        run()
