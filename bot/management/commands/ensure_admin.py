import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "ADMIN_USERNAME va ADMIN_PASSWORD bo'yicha admin yaratadi (bor bo'lsa, tegmaydi)"

    def handle(self, *args, **options):
        username, password = os.getenv("ADMIN_USERNAME"), os.getenv("ADMIN_PASSWORD")
        if not username or not password:
            return self.stdout.write("ADMIN_USERNAME/ADMIN_PASSWORD berilmagan, o'tkazib yuborildi")
        if User.objects.filter(username=username).exists():
            return self.stdout.write(f"Admin '{username}' allaqachon bor")
        User.objects.create_superuser(username=username, password=password)
        self.stdout.write(self.style.SUCCESS(f"Admin '{username}' yaratildi"))
