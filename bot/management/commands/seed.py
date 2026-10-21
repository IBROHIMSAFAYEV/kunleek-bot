from django.core.management.base import BaseCommand

from bot.models import Question, Section, Vacancy, ensure_texts


class Command(BaseCommand):
    help = "Namuna ma'lumotlar (bo'limlar, vakansiyalar, matnlar) qo'shadi"

    def handle(self, *args, **options):
        ensure_texts()
        if not Section.objects.exists():
            Section.objects.create(
                title_uz="🏢 Kompaniya haqida", title_ru="🏢 О компании", order=1,
                content_uz="Kompaniya haqida\n\nBu yerga kompaniya haqida ma'lumot yozing (admin paneldan).",
                content_ru="О компании\n\nЗдесь информация о компании (меняется в админ-панели).",
            )
            Section.objects.create(
                title_uz="📞 Aloqa", title_ru="📞 Контакты", order=2,
                content_uz="📞 Telefon: +998 00 000 00 00\n📍 Manzil: Toshkent",
                content_ru="📞 Телефон: +998 00 000 00 00\n📍 Адрес: Ташкент",
            )
        if not Vacancy.objects.exists():
            vac = Vacancy.objects.create(
                title_uz="Kassir", title_ru="Кассир", address="Toshkent",
                description_uz="Talablar:\n• Mas'uliyatlilik\n• Mijozlar bilan muloqot",
                description_ru="Требования:\n• Ответственность\n• Коммуникабельность",
            )
            Question.objects.create(vacancy=vac, text_uz="Yoshingiz nechada?", text_ru="Сколько вам лет?", answer_type="number", order=1)
            Question.objects.create(
                vacancy=vac, text_uz="Ma'lumotingiz?", text_ru="Ваше образование?", answer_type="choice", order=2,
                options_uz="O'rta\nO'rta maxsus\nOliy", options_ru="Среднее\nСреднее специальное\nВысшее",
            )
            Question.objects.create(
                vacancy=vac, text_uz="Oldin qayerda ishlagansiz? (ixtiyoriy)", text_ru="Где вы работали раньше? (необязательно)",
                is_required=False, order=3,
            )
        self.stdout.write(self.style.SUCCESS("Tayyor"))
