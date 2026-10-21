import csv

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils.http import urlencode
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.timezone import localtime
from django.shortcuts import get_object_or_404, redirect
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.decorators import action, display
from unfold.enums import ActionVariant
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from unfold.widgets import UnfoldAdminFileFieldWidget, UnfoldAdminTextareaWidget

from django.utils import timezone

from .models import (
    Announcement, Answer, Application, BotProfile, BotText, DirectMessage, Location, MessageTemplate, Question, Section,
    SectionItem, TelegramUser, Vacancy,
)
from .notify import STATUS_KINDS, notify_applicant
from .sender import send_announcement, send_messages

STATUS_COLORS = {"Yangi": "info", "Ko'rildi": "warning", "Suhbatga chaqirildi": "primary",
                 "Qabul qilindi": "success", "Rad etildi": "danger"}
MESSAGE_COLORS = {"Yuborildi": "success", "Yuborilmadi": "danger", "Yuborilmoqda": "warning", "Qabul qilindi": "info"}


def staff_name(user):
    return (user.get_full_name() or user.username) if user else ""


class CanSendMixin:
    """Bot orqali xabar yozish huquqi = "Xabar"ni qo'shish ruxsati."""

    def has_send_permission(self, request, obj=None):
        return request.user.has_perm("bot.add_directmessage")


# ---------------------------------------------------------------- xodimlar va rollar
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    list_display = ("username", "full_name", "roles", "is_active", "is_superuser", "messages_sent", "last_login")
    list_filter = ("is_active", "is_superuser", "groups")
    readonly_fields = ("last_login", "date_joined")
    fieldsets = (
        ("Kirish", {"fields": ("username", "password")}),
        ("Xodim", {"fields": (("first_name", "last_name"), "email")}),
        ("Rol va ruxsatlar", {
            "fields": ("is_active", "is_superuser", "groups", "user_permissions"),
            "description": "Xodimga bir yoki bir nechta rol bering. \"Bosh administrator\" belgilansa, hamma narsaga ruxsat "
                           "bo'ladi. Rolga qo'shimcha alohida ruxsatlarni ham shu yerda berish mumkin.",
        }),
        ("Faollik", {"fields": (("last_login", "date_joined"),)}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "first_name", "last_name", "password1", "password2", "groups")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(sent=Count("sent_messages")).prefetch_related("groups")

    @admin.display(description="Ismi")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="Rollar")
    def roles(self, obj):
        if obj.is_superuser:
            return "Bosh administrator"
        return ", ".join(g.name for g in obj.groups.all()) or "—"

    @admin.display(description="Yozgan xabarlari", ordering="sent")
    def messages_sent(self, obj):
        return obj.sent

    def save_model(self, request, obj, form, change):
        obj.is_staff = True  # admin panelga kira olishi uchun
        super().save_model(request, obj, form, change)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    list_display = ("name", "members", "perm_count")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(n_users=Count("user", distinct=True), n_perms=Count("permissions", distinct=True))

    @admin.display(description="Xodimlar", ordering="n_users")
    def members(self, obj):
        return obj.n_users

    @admin.display(description="Ruxsatlar", ordering="n_perms")
    def perm_count(self, obj):
        return obj.n_perms


# ---------------------------------------------------------------- vakansiyalar va bot mazmuni
class QuestionInline(StackedInline):
    model = Question
    extra = 0
    fields = (("text_uz", "text_ru"), ("answer_type", "is_required", "order", "is_active"), ("options_uz", "options_ru"))
    verbose_name = "Savol"
    verbose_name_plural = "Shu vakansiya uchun qo'shimcha savollar"


class QuestionScopeFilter(admin.SimpleListFilter):
    title = "Qaysi vakansiyalar uchun"
    parameter_name = "scope"

    def lookups(self, request, model_admin):
        return [("all", "Umumiy — barcha vakansiyalarda"), ("vacancy", "Faqat bitta vakansiyaga tegishli")]

    def queryset(self, request, queryset):
        if self.value() == "all":
            return queryset.filter(vacancy__isnull=True)
        if self.value() == "vacancy":
            return queryset.filter(vacancy__isnull=False)
        return queryset


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    list_display = ("text_uz", "scope", "location", "answer_type", "answers_count", "is_required", "order", "is_active")
    list_editable = ("order", "is_required", "is_active")
    list_filter = (QuestionScopeFilter, ("vacancy__location", admin.RelatedOnlyFieldListFilter), "vacancy", "answer_type", "is_required", "is_active")
    search_fields = ("text_uz", "text_ru", "options_uz", "options_ru", "vacancy__title_uz")
    list_select_related = ("vacancy", "vacancy__location")

    def get_queryset(self, request):
        # javoblar savol matni bo'yicha saqlanadi — shu matnli javoblar sonini sanaymiz
        return super().get_queryset(request).annotate(
            n_answers=Subquery(
                Answer.objects.filter(question_text=OuterRef("text_uz")).values("question_text").annotate(c=Count("id")).values("c")[:1]
            )
        )

    @admin.display(description="Vakansiya", ordering="vacancy__title_uz")
    def scope(self, obj):
        return obj.vacancy.title_uz if obj.vacancy else "Barcha vakansiyalar"

    @admin.display(description="Joy", ordering="vacancy__location__name_uz")
    def location(self, obj):
        return obj.vacancy.location.name_uz if obj.vacancy and obj.vacancy.location else "—"

    @admin.display(description="Javoblar", ordering="n_answers")
    def answers_count(self, obj):
        n = obj.n_answers or 0
        if not n:
            return 0
        url = reverse("admin:bot_answer_changelist") + "?" + urlencode({"question_text": obj.text_uz})
        return format_html('<a href="{}">{} ta</a>', url, n)


class LocationVacancyInline(TabularInline):
    model = Vacancy
    extra = 0
    fields = ("title_uz", "title_ru", "is_active")
    show_change_link = True
    verbose_name = "Vakansiya"
    verbose_name_plural = "Shu joydagi vakansiyalar"


@admin.register(Location)
class LocationAdmin(ModelAdmin):
    inlines = [LocationVacancyInline]
    list_display = ("name_uz", "address", "vacancies_count", "applications_count", "order", "is_active")
    list_editable = ("order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name_uz", "name_ru", "address")
    fieldsets = (("Joy (filial)", {
        "fields": (("name_uz", "name_ru"), "address", "map_url", ("order", "is_active")),
        "description": "Botda nomzod avval joyni tanlaydi, so'ng shu joyning faol vakansiyalari chiqadi. "
                       "Faol vakansiyasi yo'q joy botda ko'rinmaydi.",
    }),)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            n_vac=Count("vacancies", filter=Q(vacancies__is_active=True), distinct=True),
            n_apps=Count("vacancies__application", distinct=True),
        )

    @admin.display(description="Faol vakansiyalar", ordering="n_vac")
    def vacancies_count(self, obj):
        url = reverse("admin:bot_vacancy_changelist") + f"?location__id__exact={obj.pk}"
        return format_html('<a href="{}">{}</a>', url, obj.n_vac)

    @admin.display(description="Arizalar", ordering="n_apps")
    def applications_count(self, obj):
        url = reverse("admin:bot_application_changelist") + f"?vacancy__location__id__exact={obj.pk}"
        return format_html('<a href="{}">{}</a>', url, obj.n_apps)


@admin.register(Vacancy)
class VacancyAdmin(ModelAdmin):
    inlines = [QuestionInline]
    list_display = ("title_uz", "location", "address_shown", "questions_count", "applications_count", "is_active", "created_at")
    list_editable = ("is_active",)
    list_filter = (("location", admin.RelatedOnlyFieldListFilter), "is_active", "created_at")
    search_fields = ("title_uz", "title_ru", "location__name_uz", "address")
    list_select_related = ("location",)
    autocomplete_fields = ("location",)
    fieldsets = (
        ("Vakansiya", {"fields": (("title_uz", "title_ru"), "location", ("description_uz", "description_ru"), "address", "is_active")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            n_apps=Count("application", distinct=True), n_q=Count("questions", distinct=True),
        )

    @admin.display(description="Manzil")
    def address_shown(self, obj):
        return obj.full_address() or "—"

    @admin.display(description="Savollar", ordering="n_q")
    def questions_count(self, obj):
        url = reverse("admin:bot_question_changelist") + f"?vacancy__id__exact={obj.pk}"
        return format_html('<a href="{}">{}</a>', url, obj.n_q)

    @admin.display(description="Arizalar", ordering="n_apps")
    def applications_count(self, obj):
        url = reverse("admin:bot_application_changelist") + f"?vacancy__id__exact={obj.pk}"
        return format_html('<a href="{}">{}</a>', url, obj.n_apps)


class SectionItemInline(StackedInline):
    model = SectionItem
    extra = 0
    fields = (("title_uz", "title_ru"), ("content_uz", "content_ru"), "file", ("order", "is_active"))
    verbose_name = "Ichki tugma"
    verbose_name_plural = "Bo'lim ichidagi tugmalar (bo'lim ochilganda ostida chiqadi)"


@admin.register(Section)
class SectionAdmin(ModelAdmin):
    inlines = [SectionItemInline]
    fields = (("title_uz", "title_ru"), ("content_uz", "content_ru"), "file", ("order", "is_active"))
    list_display = ("title_uz", "title_ru", "items_count", "order", "is_active")
    list_editable = ("order", "is_active")

    @admin.display(description="Ichki tugmalar")
    def items_count(self, obj):
        return obj.items.count()


@admin.register(BotText)
class BotTextAdmin(ModelAdmin):
    list_display = ("key", "value_uz", "value_ru")
    search_fields = ("key", "value_uz", "value_ru")
    readonly_fields = ("key",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------- shaxsiy xabarlar
class MessageForm(forms.ModelForm):
    class Meta:
        model = DirectMessage
        fields = ("text", "file")
        widgets = {
            "text": UnfoldAdminTextareaWidget(attrs={"rows": 3, "placeholder": "Masalan: Assalomu alaykum! Ertaga soat 10:00 da suhbatga kela olasizmi?"}),
            "file": UnfoldAdminFileFieldWidget,
        }

    def clean(self):
        data = super().clean()
        if not data.get("text") and not data.get("file"):
            raise forms.ValidationError("Matn yozing yoki rasm/fayl biriktiring.")
        return data


class BroadcastForm(forms.Form):
    text = forms.CharField(label="Matn", required=False, widget=UnfoldAdminTextareaWidget(attrs={"rows": 6}))
    file = forms.FileField(label="Rasm yoki fayl", required=False, widget=UnfoldAdminFileFieldWidget)

    def clean(self):
        data = super().clean()
        if not data.get("text") and not data.get("file"):
            raise forms.ValidationError("Matn yozing yoki rasm/fayl biriktiring.")
        return data


def report(modeladmin, request, ok, failed):
    if ok:
        modeladmin.message_user(request, f"{ok} ta xabar yuborildi.", messages.SUCCESS)
    if failed:
        modeladmin.message_user(
            request, f"{failed} ta xabar yuborilmadi: foydalanuvchi botni bloklagan yoki botga hech yozmagan "
                     f"bo'lishi mumkin. Sababi \"Yozishmalar\" bo'limida ko'rinadi.", messages.ERROR,
        )


@admin.action(description="Tanlanganlarga shaxsiy xabar yuborish", permissions=["send"])
def send_message_action(modeladmin, request, queryset):
    if queryset.model is Application:
        users = TelegramUser.objects.filter(pk__in=queryset.values("user_id"))
    else:
        users = queryset
    form = BroadcastForm(request.POST, request.FILES) if "apply" in request.POST else BroadcastForm()
    if "apply" in request.POST and form.is_valid():
        msgs = []
        for user in users:
            m = DirectMessage(user=user, direction="out", text=form.cleaned_data["text"], sent_by=request.user)
            if form.cleaned_data["file"]:
                if msgs and msgs[0].file:  # bitta faylni hamma xabarlar uchun qayta ishlatamiz
                    m.file.name = msgs[0].file.name
                else:
                    m.file = form.cleaned_data["file"]
            m.save()
            msgs.append(m)
        report(modeladmin, request, *send_messages(msgs))
        return None
    return TemplateResponse(request, "admin/bot/send_message.html", {
        **modeladmin.admin_site.each_context(request),
        "title": "Shaxsiy xabar yuborish",
        "opts": modeladmin.model._meta,
        "form": form,
        "objects": queryset,
        "users": users,
        "action_name": "send_message_action",
    })


@admin.action(description="Tanlanganlarni CSV ga yuklab olish")
def export_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="arizalar.csv"'
    response.write("﻿")
    w = csv.writer(response)
    w.writerow(["Sana", "F.I.Sh.", "Telefon", "Vakansiya", "Telegram ID", "Username", "Holat", "Javoblar"])
    for a in queryset:
        w.writerow([
            a.created_at.strftime("%Y-%m-%d %H:%M"), a.full_name, a.phone, a.vacancy_title,
            a.user.tg_id, a.user.username, a.get_status_display(),
            " | ".join(f"{x.question_text}: {x.answer}" for x in a.answers.all()),
        ])
    return response


def status_action(status, label):
    @admin.action(description=f"Holatni \"{label}\" qilish", permissions=["change"])
    def action(modeladmin, request, queryset):
        changed = list(queryset.exclude(status=status).select_related("user", "vacancy"))
        queryset.update(status=status)
        modeladmin.message_user(request, f"{len(changed)} ta ariza holati \"{label}\" qilindi.", messages.SUCCESS)
        if status in STATUS_KINDS:  # nomzodlarga shablon bo'yicha xabar
            ok = failed = 0
            for app in changed:
                app.status = status
                result = notify_applicant(app, STATUS_KINDS[status], by=request.user)
                if result:
                    ok, failed = ok + result[0], failed + result[1]
            report(modeladmin, request, ok, failed)
    action.__name__ = f"mark_{status}"
    return action


def chat_link(url, unread=False):
    return format_html(
        '<a class="kb-chat-link{}" href="{}"><span class="material-symbols-outlined">{}</span>{}</a>',
        " kb-unread" if unread else "", url, "mark_chat_unread" if unread else "chat", "Javob kutmoqda" if unread else "Yozish",
    )


def sender_label(m):
    if m.direction == "in":
        return m.user.full_name or "Foydalanuvchi"
    if m.is_auto:
        return "Bot (avtomatik)" + (f" · {staff_name(m.sent_by)}" if m.sent_by else "")
    return staff_name(m.sent_by) or "Admin"


def render_chat(msgs, app=None):
    """Yozishmani messenjer ko'rinishida chizadi: HR o'ngda, foydalanuvchi chapda; ostida tezkor javob tugmalari."""
    if not msgs:
        chat = format_html(
            '<div class="kb-chat-empty"><span class="material-symbols-outlined">forum</span>'
            '<p>Hali yozishma yo\'q. Pastdagi maydondan birinchi xabarni yozing.</p></div>'
        )
    else:
        bubbles = format_html_join("", (
            '<div class="kb-msg kb-{}"><div class="kb-bubble">'
            '<div class="kb-who">{}</div>{}<div class="kb-text">{}</div>'
            '<div class="kb-meta">{}{}</div></div></div>'
        ), (
            (m.direction, sender_label(m),
             format_html('<a class="kb-file" href="{}" target="_blank"><span class="material-symbols-outlined">attach_file</span>{}</a>',
                         m.file.url, m.file.name.rsplit("/", 1)[-1]) if m.file else "",
             m.text, localtime(m.created_at).strftime("%d.%m.%Y %H:%M"),
             format_html(' · <span class="kb-st-{}">{}</span>', m.status, m.get_status_display()) if m.direction == "out" else "")
            for m in msgs
        ))
        chat = format_html('<div class="kb-chat">{}</div>', bubbles)
    lang = (msgs[0].user.language if msgs else (app.user.language if app else "")) or "uz"
    quick = format_html_join("", '<button type="button" class="kb-quick-btn" data-kb-quick="{}">{}</button>', (
        (t.render(app, lang), t.title) for t in MessageTemplate.objects.filter(kind="quick", is_active=True)
    ))
    if quick:
        quick = format_html('<div class="kb-quick"><span class="kb-kpi-hint">Tezkor javob:</span>{}</div>', quick)
    return format_html("{}{}", chat, quick)


def save_message_formset(modeladmin, request, form, formset):
    """'Yangi xabar' inline'idagi xabarlarni saqlab, darhol Telegram orqali yuboradi."""
    if not issubclass(formset.form, MessageForm):
        return formset.save()
    msgs = formset.save(commit=False)
    for m in msgs:
        m.direction, m.sent_by = "out", request.user
        if isinstance(form.instance, Application):
            m.user = form.instance.user
        m.save()
    if msgs:
        report(modeladmin, request, *send_messages(msgs))


class NewMessageInline(StackedInline):
    model = DirectMessage
    form = MessageForm
    extra = 1
    max_num = 1
    can_delete = False
    verbose_name = "Yangi xabar"
    verbose_name_plural = "Bot orqali xabar yozish — \"Saqlash\" bosilganda darhol yuboriladi"

    def get_queryset(self, request):
        return super().get_queryset(request).none()


class AnswerInline(TabularInline):
    model = Answer
    extra = 0
    can_delete = False
    fields = readonly_fields = ("question_text", "answer", "file")
    verbose_name_plural = "Savollarga javoblar"

    def has_add_permission(self, request, obj=None):
        return False


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = "__all__"

    def clean_interview_at(self):
        value = self.cleaned_data.get("interview_at")
        if value and "interview_at" in self.changed_data and value < timezone.now():
            raise forms.ValidationError("Suhbat vaqti kelajakda bo'lishi kerak.")
        return value


@admin.register(Application)
class ApplicationAdmin(CanSendMixin, ModelAdmin):
    form = ApplicationForm
    inlines = [AnswerInline, NewMessageInline]
    list_display = ("full_name", "phone", "vacancy_title", "location", "status_badge", "interview", "created_at", "write")
    list_display_links = ("full_name",)
    list_filter = ("status", ("vacancy__location", admin.RelatedOnlyFieldListFilter), "vacancy", "created_at", "interview_at")
    search_fields = ("full_name", "phone", "vacancy_title")
    date_hierarchy = "created_at"
    actions = [
        send_message_action, status_action("viewed", "Ko'rildi"), status_action("accepted", "Qabul qilindi"),
        status_action("rejected", "Rad etildi"), export_csv,
    ]
    readonly_fields = ("user", "created_at", "conversation", "reminder_sent")
    fieldsets = (
        ("Nomzod", {"fields": (("full_name", "phone"), ("vacancy", "vacancy_title"), ("status", "created_at"), "user")}),
        ("Suhbat", {
            "fields": (("interview_at", "interview_place"), "reminder_sent"),
            "description": "Vaqtni belgilab saqlasangiz, nomzodga taklif o'zi boradi va holat \"Suhbatga chaqirildi\" bo'ladi. "
                           "Suhbatdan 24 soat oldin eslatma yuboriladi.",
        }),
        ("Yozishma", {"fields": ("conversation",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "vacancy", "vacancy__location")

    @admin.display(description="Joy", ordering="vacancy__location__name_uz")
    def location(self, obj):
        return obj.vacancy.location.name_uz if obj.vacancy and obj.vacancy.location else "—"

    @display(description="Holat", label=STATUS_COLORS)
    def status_badge(self, obj):
        return obj.get_status_display()

    @admin.display(description="Suhbat", ordering="interview_at")
    def interview(self, obj):
        return localtime(obj.interview_at).strftime("%d.%m %H:%M") if obj.interview_at else "—"

    @admin.display(description="Xabar")
    def write(self, obj):
        last = obj.user.messages.order_by("-created_at").first()
        return chat_link(reverse("admin:bot_application_change", args=[obj.pk]) + "#messages-group",
                         unread=bool(last and last.direction == "in"))

    @admin.display(description="Yozishma")
    def conversation(self, obj):
        if not obj.pk:
            return render_chat([])
        return render_chat(list(obj.user.messages.select_related("user", "sent_by").order_by("created_at")), app=obj)

    def _notify(self, request, app, kind):
        result = notify_applicant(app, kind, by=request.user)
        if result is None:
            self.message_user(request, "Bu turdagi avtomatik xabar shabloni o'chirilgan — nomzodga xabar yuborilmadi.",
                              messages.WARNING)
        else:
            report(self, request, *result)

    def save_model(self, request, obj, form, change):
        old_status = Application.objects.filter(pk=obj.pk).values_list("status", flat=True).first() if change else None
        if change and obj.status == "new" and "status" not in form.changed_data:  # admin ochib saqladi — demak ko'rildi
            obj.status = "viewed"
        invite = "interview_at" in form.changed_data and obj.interview_at
        if invite:
            obj.reminder_sent = False
            if obj.status in ("new", "viewed"):
                obj.status = "interview"
        super().save_model(request, obj, form, change)
        if invite:
            self._notify(request, obj, "interview_invite")
        if old_status and old_status != obj.status and obj.status in STATUS_KINDS:
            self._notify(request, obj, STATUS_KINDS[obj.status])

    def save_formset(self, request, form, formset, change):
        save_message_formset(self, request, form, formset)


class UserNewMessageInline(NewMessageInline):
    fk_name = "user"


class HasPhoneFilter(admin.SimpleListFilter):
    title = "Telefon raqami"
    parameter_name = "has_phone"

    def lookups(self, request, model_admin):
        return [("yes", "Bor"), ("no", "Yo'q")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(phone="")
        if self.value() == "no":
            return queryset.filter(phone="")
        return queryset


@admin.action(description="Tanlanganlarni CSV ga yuklab olish")
def export_users_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="foydalanuvchilar.csv"'
    response.write("﻿")
    w = csv.writer(response)
    w.writerow(["Qo'shilgan", "Ism", "Username", "Telefon", "Telegram ID", "Til", "Arizalar"])
    for u in queryset.annotate(apps=Count("applications")):
        w.writerow([localtime(u.created_at).strftime("%Y-%m-%d %H:%M"), u.full_name,
                    f"@{u.username}" if u.username else "", u.phone, u.tg_id, u.get_language_display(), u.apps])
    return response


@admin.register(TelegramUser)
class TelegramUserAdmin(CanSendMixin, ModelAdmin):
    inlines = [UserNewMessageInline]
    list_display = ("full_name", "username_link", "phone", "language", "apps_count", "created_at", "write")
    list_filter = (HasPhoneFilter, "language", "created_at")
    search_fields = ("full_name", "username", "tg_id", "phone")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50
    readonly_fields = ("tg_id", "created_at", "conversation")
    actions = [send_message_action, export_users_csv]
    fieldsets = (
        ("Foydalanuvchi", {"fields": (("full_name", "username"), ("phone", "language"), ("tg_id", "created_at"))}),
        ("Yozishma", {"fields": ("conversation",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(apps=Count("applications"))

    @admin.display(description="Username", ordering="username")
    def username_link(self, obj):
        if not obj.username:
            return "—"
        return format_html('<a href="https://t.me/{0}" target="_blank" rel="noopener">@{0}</a>', obj.username)

    @admin.display(description="Arizalar", ordering="apps")
    def apps_count(self, obj):
        return obj.apps

    def changelist_view(self, request, extra_context=None):
        from .dashboard import user_stats

        s = user_stats()
        extra_context = {**(extra_context or {}), "subtitle": None,
                         "title": f"Foydalanuvchilar — jami {s['total']}, bugun +{s['today']}, raqami bor {s['with_phone']}"}
        return super().changelist_view(request, extra_context)

    @admin.display(description="Xabar")
    def write(self, obj):
        last = obj.messages.order_by("-created_at").first()
        return chat_link(reverse("admin:bot_telegramuser_change", args=[obj.pk]) + "#messages-group",
                         unread=bool(last and last.direction == "in"))

    @admin.display(description="Yozishma")
    def conversation(self, obj):
        if not obj.pk:
            return render_chat([])
        app = obj.applications.select_related("vacancy").order_by("-created_at").first()
        return render_chat(list(obj.messages.select_related("user", "sent_by").order_by("created_at")), app=app)

    def save_formset(self, request, form, formset, change):
        save_message_formset(self, request, form, formset)


class SentByFilter(admin.SimpleListFilter):
    title = "Kim yozdi"
    parameter_name = "sent_by"

    def lookups(self, request, model_admin):
        staff = User.objects.filter(sent_messages__isnull=False).distinct()
        return [("auto", "Bot (avtomatik)")] + [(str(u.pk), staff_name(u)) for u in staff]

    def queryset(self, request, queryset):
        if self.value() == "auto":
            return queryset.filter(is_auto=True)
        if self.value():
            return queryset.filter(sent_by_id=self.value(), is_auto=False)
        return queryset


@admin.register(DirectMessage)
class DirectMessageAdmin(ModelAdmin):
    list_display = ("created_at", "user", "direction_badge", "author", "short_text", "status_badge", "open_chat")
    list_filter = ("direction", SentByFilter, "status", "created_at")
    list_select_related = ("user", "sent_by")

    @admin.display(description="Kim yozdi")
    def author(self, obj):
        return "—" if obj.direction == "in" else sender_label(obj)
    search_fields = ("text", "user__full_name", "user__username", "user__tg_id")
    autocomplete_fields = ("user",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @display(description="Yo'nalish", label={"Kiruvchi": "info", "Chiquvchi": "primary"})
    def direction_badge(self, obj):
        return "Kiruvchi" if obj.direction == "in" else "Chiquvchi"

    @display(description="Holat", label=MESSAGE_COLORS)
    def status_badge(self, obj):
        return obj.get_status_display()

    @admin.display(description="Matn")
    def short_text(self, obj):
        return (obj.text[:80] + "…") if len(obj.text) > 80 else (obj.text or "Fayl")

    @admin.display(description="Suhbat")
    def open_chat(self, obj):
        if obj.application_id:
            url = reverse("admin:bot_application_change", args=[obj.application_id])
        else:
            url = reverse("admin:bot_telegramuser_change", args=[obj.user_id])
        return chat_link(url + "#messages-group")

    def get_fields(self, request, obj=None):
        if obj:
            return ("user", "application", "direction", "sent_by", "is_auto", "text", "file", "status", "error", "created_at")
        return ("user", "text", "file")

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj) if obj else ()

    def get_form(self, request, obj=None, **kwargs):
        if not obj:
            kwargs["form"] = type("NewDirectMessageForm", (MessageForm,), {
                "Meta": type("Meta", (MessageForm.Meta,), {"fields": ("user", "text", "file")}),
            })
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        if change:
            return
        obj.direction, obj.sent_by = "out", request.user
        obj.save()
        report(self, request, *send_messages([obj]))


# ---------------------------------------------------------------- e'lonlar
@admin.register(Announcement)
class AnnouncementAdmin(ModelAdmin):
    list_display = ("preview", "audience_badge", "status_badge", "sent_count", "failed_count", "sent_at", "sent_by")
    list_filter = ("status", "audience")
    search_fields = ("text_uz", "text_ru")
    readonly_fields = ("status", "sent_count", "failed_count", "sent_at", "sent_by", "created_at")
    actions_detail = ["send_now"]
    fieldsets = (
        ("E'lon", {
            "fields": (("text_uz", "text_ru"), "file", "audience"),
            "description": "Saqlang, so'ng yuqoridagi \"Hammaga yuborish\" tugmasini bosing — "
                           "yuborishdan oldin tasdiqlash sahifasi chiqadi.",
        }),
        ("Natija", {"fields": (("status", "sent_at"), ("sent_count", "failed_count"), ("sent_by", "created_at"))}),
    )

    def has_send_permission(self, request, object_id=None):
        return request.user.has_perm("bot.send_announcement")

    @admin.display(description="E'lon")
    def preview(self, obj):
        return (obj.text_uz[:90] + "…") if len(obj.text_uz) > 90 else obj.text_uz

    @display(description="Kimga", label={"Hammaga": "primary", "Faqat o'zbek tilidagilarga": "info",
                                         "Faqat rus tilidagilarga": "info"})
    def audience_badge(self, obj):
        return obj.get_audience_display()

    @display(description="Holat", label={"Qoralama": "warning", "Yuborilgan": "success"})
    def status_badge(self, obj):
        return obj.get_status_display()

    def response_add(self, request, obj, post_url_continue=None):
        # yangi e'lon saqlangach, darhol tasdiqlash sahifasiga o'tamiz
        if ("_addanother" not in request.POST and "_continue" not in request.POST
                and self.has_send_permission(request)):
            return redirect("admin:bot_announcement_send_now", object_id=obj.pk)
        return super().response_add(request, obj, post_url_continue)

    @action(description="Hammaga yuborish", url_path="send", icon="campaign", variant=ActionVariant.PRIMARY,
            permissions=["send"])
    def send_now(self, request, object_id):
        ann = get_object_or_404(Announcement, pk=object_id)
        if request.method == "POST":
            sent, failed = send_announcement(ann, by=request.user)
            self.message_user(request, f"E'lon {sent} ta foydalanuvchiga yetkazildi.", messages.SUCCESS)
            if failed:
                self.message_user(request, f"{failed} ta foydalanuvchiga yetmadi (botni bloklagan yoki "
                                           f"akkaunti o'chirilgan).", messages.WARNING)
            return redirect("admin:bot_announcement_change", object_id=ann.pk)
        recipients = ann.recipients()
        return TemplateResponse(request, "admin/bot/announcement_confirm.html", {
            **self.admin_site.each_context(request),
            "title": "E'lonni yuborish",
            "opts": self.model._meta,
            "ann": ann,
            "total": recipients.count(),
            "total_ru": recipients.filter(language="ru").count(),
        })


# ---------------------------------------------------------------- bot profili (Telegramdagi nom, avatar, tavsif)
@admin.register(BotProfile)
class BotProfileAdmin(ModelAdmin):
    readonly_fields = ("preview", "synced_at", "last_error")
    actions_detail = ["pull_now"]
    fieldsets = (
        ("Telegramda shunday ko'rinadi", {"fields": ("preview",)}),
        ("Nom va avatar", {"fields": (("name_uz", "name_ru"), "photo")}),
        ("Profildagi qisqa tavsif (About)", {"fields": (("short_description_uz", "short_description_ru"),)}),
        ("Bot haqida — botni birinchi ochganda, START dan oldin", {"fields": (("description_uz", "description_ru"),)}),
        ("Holat", {"fields": (("synced_at", "last_error"),),
                   "description": "\"Saqlash\" bosilganda o'zgarishlar darhol Telegramga yuboriladi. "
                                  "Telegram bot nomini kuniga bir necha martagina o'zgartirishga ruxsat beradi."}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        profile = BotProfile.objects.first()
        if not profile:
            from .profile import pull_from_telegram

            try:
                data = pull_from_telegram()
            except Exception as e:  # noqa
                data = {"name_uz": "Bot"}
                self.message_user(request, f"Telegramdan hozirgi profil olinmadi: {e}", messages.WARNING)
            profile = BotProfile.objects.create(**{k: v or "" for k, v in data.items()})
        return redirect("admin:bot_botprofile_change", object_id=profile.pk)

    @admin.display(description="Ko'rinish")
    def preview(self, obj):
        avatar = (format_html('<img src="{}" alt="">', obj.photo.url) if obj.photo
                  else format_html("<span>{}</span>", (obj.name_uz or "B")[:1].upper()))
        return format_html(
            '<div class="kb-tgprofile"><div class="kb-tg-avatar">{}</div><div class="kb-tg-name">{}</div>'
            '<div class="kb-tg-sub">bot</div><div class="kb-tg-about">{}</div></div>'
            '<div class="kb-tg-start"><div class="kb-tg-start-title">Bu bot nima qila oladi?</div>'
            '<div class="kb-text">{}</div></div>',
            avatar, obj.name_uz, obj.short_description_uz or "Qisqa tavsif yozilmagan",
            obj.description_uz or "Tavsif yozilmagan",
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from .profile import push_to_telegram

        changed, error = push_to_telegram(obj)
        if error:
            self.message_user(request, f"Telegramga yuborilmadi: {error}", messages.ERROR)
        elif changed:
            self.message_user(request, "Telegramda yangilandi: " + ", ".join(changed) + ".", messages.SUCCESS)
        else:
            self.message_user(request, "Telegramdagi profil allaqachon shu holatda.", messages.INFO)

    @action(description="Telegramdan qayta o'qish", url_path="pull", icon="sync", permissions=["change"])
    def pull_now(self, request, object_id):
        from .profile import pull_from_telegram

        profile = get_object_or_404(BotProfile, pk=object_id)
        try:
            for k, v in pull_from_telegram().items():
                setattr(profile, k, v or "")
            if not profile.name_uz:
                profile.name_uz = "Bot"
            profile.save()
            self.message_user(request, "Telegramdagi hozirgi nom va tavsiflar yuklandi.", messages.SUCCESS)
        except Exception as e:  # noqa
            self.message_user(request, f"Telegramdan o'qib bo'lmadi: {e}", messages.ERROR)
        return redirect("admin:bot_botprofile_change", object_id=profile.pk)


# ---------------------------------------------------------------- xabar shablonlari
@admin.register(MessageTemplate)
class MessageTemplateAdmin(ModelAdmin):
    list_display = ("title", "kind_badge", "short_text", "order", "is_active")
    list_editable = ("order", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("title", "text_uz", "text_ru")
    fieldsets = (
        (None, {
            "fields": (("kind", "title"), ("text_uz", "text_ru"), ("order", "is_active")),
            "description": "Matnga qo'yish mumkin: " + MessageTemplate.PLACEHOLDERS + ". Ular nomzod ma'lumoti bilan "
                           "almashtiriladi. Avtomatik turlardan har biri uchun birinchi faol shablon ishlatiladi; "
                           "\"Tezkor javob\" turidagilar yozishma ostida tugma bo'lib chiqadi.",
        }),
    )

    @display(description="Turi", label=True)
    def kind_badge(self, obj):
        return "Tezkor javob" if obj.kind == "quick" else "Avtomatik"

    @admin.display(description="Matn")
    def short_text(self, obj):
        return (obj.text_uz[:80] + "…") if len(obj.text_uz) > 80 else obj.text_uz


# ---------------------------------------------------------------- ariza javoblari (barcha savollarga berilgan javoblar)
class QuestionTextFilter(admin.SimpleListFilter):
    title = "Savol"
    parameter_name = "question_text"

    def lookups(self, request, model_admin):
        texts = Answer.objects.values_list("question_text", flat=True).distinct().order_by("question_text")
        return [(t, t if len(t) <= 60 else t[:60] + "…") for t in texts]

    def queryset(self, request, queryset):
        return queryset.filter(question_text=self.value()) if self.value() else queryset


@admin.action(description="Tanlanganlarni CSV ga yuklab olish")
def export_answers_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="javoblar.csv"'
    response.write("﻿")
    w = csv.writer(response)
    w.writerow(["Sana", "Nomzod", "Telefon", "Vakansiya", "Joy", "Savol", "Javob", "Fayl"])
    for a in queryset.select_related("application", "application__vacancy", "application__vacancy__location"):
        app = a.application
        vac = app.vacancy
        w.writerow([
            localtime(app.created_at).strftime("%Y-%m-%d %H:%M"), app.full_name, app.phone, app.vacancy_title,
            vac.location.name_uz if vac and vac.location else "", a.question_text, a.answer,
            request.build_absolute_uri(a.file.url) if a.file else "",
        ])
    return response


@admin.register(Answer)
class AnswerAdmin(ModelAdmin):
    list_display = ("question_text", "short_answer", "file_link", "applicant", "vacancy", "location", "created")
    list_filter = (
        QuestionTextFilter,
        ("application__vacancy__location", admin.RelatedOnlyFieldListFilter),
        ("application__vacancy", admin.RelatedOnlyFieldListFilter),
        "application__created_at",
    )
    search_fields = ("question_text", "answer", "application__full_name", "application__phone")
    list_select_related = ("application", "application__vacancy", "application__vacancy__location")
    actions = [export_answers_csv]
    list_per_page = 50
    ordering = ("-application__created_at", "id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Javob")
    def short_answer(self, obj):
        return (obj.answer[:70] + "…") if len(obj.answer) > 70 else obj.answer

    @admin.display(description="Fayl")
    def file_link(self, obj):
        return format_html('<a href="{}" target="_blank">ochish</a>', obj.file.url) if obj.file else "—"

    @admin.display(description="Nomzod", ordering="application__full_name")
    def applicant(self, obj):
        url = reverse("admin:bot_application_change", args=[obj.application_id])
        return format_html('<a href="{}">{}</a>', url, obj.application.full_name)

    @admin.display(description="Vakansiya", ordering="application__vacancy_title")
    def vacancy(self, obj):
        return obj.application.vacancy_title or "—"

    @admin.display(description="Joy")
    def location(self, obj):
        vac = obj.application.vacancy
        return vac.location.name_uz if vac and vac.location else "—"

    @admin.display(description="Sana", ordering="application__created_at")
    def created(self, obj):
        return localtime(obj.application.created_at).strftime("%d.%m.%Y %H:%M")