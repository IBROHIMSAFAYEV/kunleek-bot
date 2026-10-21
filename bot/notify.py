"""Nomzodga avtomatik xabarlar: holat o'zgarishi, suhbatga taklif va eslatma."""
from datetime import timedelta

from django.utils import timezone

from .models import Application, DirectMessage, MessageTemplate
from .sender import send_messages

STATUS_KINDS = {"accepted": "status_accepted", "rejected": "status_rejected"}


def template_for(kind):
    return MessageTemplate.objects.filter(kind=kind, is_active=True).order_by("order", "id").first()


def notify_applicant(app: Application, kind, by=None):
    """Shablon bo'yicha nomzodga xabar yuboradi (yozishmada ham ko'rinadi). (yuborildi, xato) yoki None."""
    tpl = template_for(kind)
    if not tpl:
        return None
    text = tpl.render(app, app.user.language or "uz")
    msg = DirectMessage.objects.create(
        user=app.user, application=app, direction="out", text=text, sent_by=by, is_auto=True,
    )
    return send_messages([msg])


def send_due_reminders():
    """Suhbatiga 24 soatdan kam qolgan nomzodlarga eslatma yuboradi. Yuborilganlar sonini qaytaradi."""
    now = timezone.now()
    due = Application.objects.select_related("user", "vacancy").filter(
        interview_at__gt=now, interview_at__lte=now + timedelta(hours=24), reminder_sent=False,
    )
    sent = 0
    for app in due:
        result = notify_applicant(app, "interview_reminder")
        Application.objects.filter(pk=app.pk).update(reminder_sent=True)  # qayta-qayta yubormaslik uchun
        sent += bool(result and result[0])
    return sent
