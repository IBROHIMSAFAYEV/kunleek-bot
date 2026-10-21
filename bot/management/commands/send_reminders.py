from django.core.management.base import BaseCommand

from bot.notify import send_due_reminders


class Command(BaseCommand):
    help = "Suhbatiga 24 soatdan kam qolgan nomzodlarga eslatma yuboradi (serverda soatlik/kunlik vazifa qilib qo'ying)"

    def handle(self, *args, **options):
        self.stdout.write(f"Eslatma yuborildi: {send_due_reminders()}")
