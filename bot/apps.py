from django.apps import AppConfig
from django.db.models.signals import post_migrate


class BotConfig(AppConfig):
    name = "bot"
    verbose_name = "Telegram bot"

    def ready(self):
        from .roles import ensure_roles_and_templates

        # ruxsatlar yaratilgandan keyin ishlashi uchun post_migrate da
        post_migrate.connect(ensure_roles_and_templates, sender=self)
