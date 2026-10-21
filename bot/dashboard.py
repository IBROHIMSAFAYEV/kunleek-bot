"""Admin bosh sahifasi (dashboard) va yon menyudagi raqamlar."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Max, OuterRef, Subquery
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from .models import Application, DirectMessage, TelegramUser


def unanswered_users():
    """Oxirgi xabari foydalanuvchidan kelgan (admin hali javob bermagan) foydalanuvchilar."""
    last_dir = DirectMessage.objects.filter(user=OuterRef("pk")).order_by("-created_at").values("direction")[:1]
    return TelegramUser.objects.annotate(last_dir=Subquery(last_dir)).filter(last_dir="in")


def user_stats():
    """Botga /start bosgan foydalanuvchilar statistikasi (dashboard va /stats uchun)."""
    today = timezone.localdate()
    users = TelegramUser.objects.all()
    return {
        "total": users.count(),
        "today": users.filter(created_at__date=today).count(),
        "week": users.filter(created_at__date__gt=today - timedelta(days=7)).count(),
        "month": users.filter(created_at__date__gt=today - timedelta(days=30)).count(),
        "with_phone": users.exclude(phone="").count(),
        "applied": users.filter(applications__isnull=False).distinct().count(),
        "uz": users.filter(language="uz").count(),
        "ru": users.filter(language="ru").count(),
        "no_lang": users.filter(language="").count(),
    }


def daily_chart(qs, days):
    """So'nggi kunlar bo'yicha yozuvlar soni: [{day, n, pct}]."""
    per_day = dict(
        qs.filter(created_at__date__gte=days[0]).annotate(day=TruncDate("created_at"))
        .values("day").annotate(n=Count("id")).values_list("day", "n")
    )
    peak = max(per_day.values(), default=0) or 1
    return [{"day": d, "n": per_day.get(d, 0), "pct": round(per_day.get(d, 0) * 100 / peak)} for d in days], sum(per_day.values())


def since(url, today, days_back):
    """Ro'yxatni 'oxirgi N kun' bo'yicha filtrlaydigan havola (admin sana filtri formatida)."""
    start, end = today - timedelta(days=days_back), today + timedelta(days=1)
    return f"{url}?created_at__gte={start.isoformat()}&created_at__lt={end.isoformat()}"


def badge_new_applications(request):
    return Application.objects.filter(status="new").count() or None


def badge_unanswered(request):
    return unanswered_users().count() or None


def dashboard_callback(request, context):
    now = timezone.localtime()
    today = now.date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    chart, chart_total = daily_chart(Application.objects.all(), days)
    users_chart, users_chart_total = daily_chart(TelegramUser.objects.all(), days)
    stats = user_stats()
    users_url = reverse("admin:bot_telegramuser_changelist")

    waiting = (
        unanswered_users()
        .annotate(last_at=Max("messages__created_at"))
        .order_by("-last_at")[:6]
    )
    waiting_rows = []
    for u in waiting:
        last = u.messages.filter(direction="in").order_by("-created_at").first()
        app = u.applications.order_by("-created_at").first()
        url = (reverse("admin:bot_application_change", args=[app.pk]) if app
               else reverse("admin:bot_telegramuser_change", args=[u.pk])) + "#messages-group"
        waiting_rows.append({"user": u, "text": last.text if last else "", "at": last.created_at if last else None, "url": url})

    context.update({
        "kpis": [
            {"title": "Yangi arizalar", "value": Application.objects.filter(status="new").count(), "icon": "fiber_new",
             "hint": "Ko'rib chiqilmagan", "url": reverse("admin:bot_application_changelist") + "?status__exact=new"},
            {"title": "Bugungi arizalar", "value": Application.objects.filter(created_at__date=today).count(),
             "icon": "today", "hint": now.strftime("%d.%m.%Y"), "url": reverse("admin:bot_application_changelist")},
            {"title": "Javob kutmoqda", "value": unanswered_users().count(), "icon": "mark_chat_unread",
             "hint": "Foydalanuvchi yozgan, javob yo'q", "url": reverse("admin:bot_directmessage_changelist") + "?direction__exact=in"},
            {"title": "Foydalanuvchilar", "value": stats["total"], "icon": "group",
             "hint": f"Bugun +{stats['today']} · raqami bor: {stats['with_phone']}",
             "url": reverse("admin:bot_telegramuser_changelist")},
        ],
        "chart": chart,
        "chart_total": chart_total,
        "users_chart": users_chart,
        "users_chart_total": users_chart_total,
        "user_stats": [
            {"label": "Jami", "n": stats["total"], "url": users_url},
            {"label": "Bugun", "n": stats["today"], "url": since(users_url, today, 0)},
            {"label": "7 kun", "n": stats["week"], "url": since(users_url, today, 6)},
            {"label": "30 kun", "n": stats["month"], "url": since(users_url, today, 29)},
            {"label": "Raqami bor", "n": stats["with_phone"], "url": users_url + "?has_phone=yes"},
            {"label": "Ariza bergan", "n": stats["applied"], "url": reverse("admin:bot_application_changelist")},
            {"label": "O'zbekcha", "n": stats["uz"], "url": users_url + "?language__exact=uz"},
            {"label": "Ruscha", "n": stats["ru"], "url": users_url + "?language__exact=ru"},
        ],
        "recent_apps": Application.objects.select_related("user").order_by("-created_at")[:7],
        "upcoming": Application.objects.filter(interview_at__gte=now).order_by("interview_at")[:6],
        "staff_activity": [
            {"name": u.get_full_name() or u.username, "n": u.n}
            for u in User.objects.filter(sent_messages__created_at__gte=now - timedelta(days=7), sent_messages__is_auto=False)
            .annotate(n=Count("sent_messages")).order_by("-n")[:8]
        ],
        "waiting": waiting_rows,
        "pipeline": [
            {"label": label, "key": key, "n": counts.get(key, 0),
             "url": reverse("admin:bot_application_changelist") + f"?status__exact={key}"}
            for counts in [dict(Application.objects.values_list("status").annotate(n=Count("id")))]
            for key, label in Application.STATUS
        ],
    })
    return context
