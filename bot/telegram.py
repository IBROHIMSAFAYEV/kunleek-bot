import asyncio
import logging
import re
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
    Message, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from asgiref.sync import sync_to_async
from django.db.models import Count, Q
from django.conf import settings

from .models import (
    Answer, Application, BotText, DirectMessage, Location, Question, Section, SectionItem, TelegramUser, Vacancy,
    ensure_texts, file_path,
)
from .sender import deliver, make_bot
from .storage import DBStorage
from .texts import DEFAULTS, LANGS

log = logging.getLogger(__name__)
router = Router()


class Apply(StatesGroup):
    name = State()
    phone = State()
    question = State()


# ---------------------------------------------------------------- DB helpers
@sync_to_async
def db_user(tg, create=True):
    user, _ = TelegramUser.objects.get_or_create(
        tg_id=tg.id, defaults={"full_name": tg.full_name, "username": tg.username or ""}
    )
    return user


@sync_to_async
def db_set_lang(tg_id, lang):
    TelegramUser.objects.filter(tg_id=tg_id).update(language=lang)


@sync_to_async
def db_text(key, lang):
    obj = BotText.objects.filter(key=key).first()
    if obj:
        return obj.value(lang)
    return DEFAULTS[key]["ru" if lang == "ru" else "uz"]


@sync_to_async
def db_labels(key):
    """Kalitning barcha tillardagi qiymatlari (tugma bosilganini aniqlash uchun)."""
    obj = BotText.objects.filter(key=key).first()
    if obj:
        return {obj.value_uz, obj.value_ru}
    return {DEFAULTS[key][l] for l in LANGS}


@sync_to_async
def db_sections():
    return list(Section.objects.filter(is_active=True))


@sync_to_async
def db_section(pk):
    """Bo'lim, uning fayli va faol ichki tugmalari."""
    sec = Section.objects.filter(pk=pk, is_active=True).first()
    if not sec:
        return None, None, []
    return sec, file_path(sec.file), list(sec.items.filter(is_active=True))


@sync_to_async
def db_item(pk):
    item = SectionItem.objects.filter(pk=pk, is_active=True, section__is_active=True).first()
    return item, file_path(item.file) if item else None


@sync_to_async
def db_save_incoming(user, text, file_name=""):
    """Javobni foydalanuvchining oxirgi arizasiga bog'laymiz, shunda u ariza sahifasida ko'rinadi."""
    app = user.applications.order_by("-created_at").first()
    msg = DirectMessage(user=user, application=app, direction="in", text=text, status="received")
    msg.file.name = file_name
    msg.save()


MAX_FILE = 20 * 1024 * 1024  # Telegram bot 20 MB gacha faylni yuklab ola oladi


def incoming_file(message: Message):
    """Xabardagi fayl yoki rasm: (file_id, fayl nomi, hajmi) yoki None."""
    if message.document:
        d = message.document
        return d.file_id, d.file_name or f"{d.file_unique_id}.bin", d.file_size or 0
    if message.photo:
        p = message.photo[-1]  # eng katta o'lcham
        return p.file_id, f"photo_{p.file_unique_id}.jpg", p.file_size or 0
    return None


async def save_tg_file(bot: Bot, file_id, name, folder):
    """Telegramdagi faylni yuklab, media/<folder>/ ga saqlaydi va saqlangan nomni qaytaradi."""
    import io

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    buf = io.BytesIO()
    await bot.download(file_id, destination=buf)
    return await sync_to_async(default_storage.save)(f"{folder}/{name}", ContentFile(buf.getvalue()))


@sync_to_async
def db_locations():
    """Faol vakansiyasi bor faol joylar (har biri vakansiyalar soni bilan)."""
    return list(
        Location.objects.filter(is_active=True)
        .annotate(n=Count("vacancies", filter=Q(vacancies__is_active=True)))
        .filter(n__gt=0)
    )


@sync_to_async
def db_location(pk):
    return Location.objects.filter(pk=pk, is_active=True).first()


@sync_to_async
def db_vacancies(location_id=None):
    qs = Vacancy.objects.filter(is_active=True)
    if location_id:
        qs = qs.filter(location_id=location_id)
    return list(qs)


@sync_to_async
def db_vacancy(pk):
    return Vacancy.objects.select_related("location").filter(pk=pk, is_active=True).first()


@sync_to_async
def db_questions(vacancy_id):
    qs = Question.objects.filter(is_active=True).filter(Q(vacancy_id=vacancy_id) | Q(vacancy__isnull=True))
    return list(qs.order_by("order", "id"))


@sync_to_async
def db_question(pk):
    return Question.objects.filter(pk=pk).first()


@sync_to_async
def db_save_application(user, vacancy_id, full_name, phone, answers):
    vac = Vacancy.objects.filter(pk=vacancy_id).first()
    app = Application.objects.create(
        user=user, vacancy=vac, vacancy_title=vac.title_uz if vac else "",
        full_name=full_name, phone=phone,
    )
    objs = []
    for q, a, *rest in answers:  # [savol, javob] yoki [savol, javob, fayl_nomi]
        ans = Answer(application=app, question_text=q, answer=a)
        ans.file.name = rest[0] if rest else ""
        objs.append(ans)
    Answer.objects.bulk_create(objs)
    TelegramUser.objects.filter(pk=user.pk).update(phone=phone)
    return app


# ---------------------------------------------------------------- send helpers
async def send(message: Message, text: str, **kw):
    """Admin paneldagi matnni oddiy matn sifatida (HTML'siz) yuboradi."""
    return await message.answer(text, parse_mode=None, **kw)


async def main_menu_kb(lang):
    rows = [[KeyboardButton(text=await db_text("menu_vacancies", lang))]]
    secs = [KeyboardButton(text=s.title(lang)) for s in await db_sections()]
    for i in range(0, len(secs), 2):
        rows.append(secs[i:i + 2])
    rows.append([KeyboardButton(text=await db_text("menu_language", lang))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
    ]])


async def show_menu(message: Message, lang, text_key="main_menu"):
    await send(message, await db_text(text_key, lang), reply_markup=await main_menu_kb(lang))


async def ask_language(message: Message):
    await message.answer(await db_text("choose_language", "uz"), reply_markup=lang_kb())


# ---------------------------------------------------------------- handlers
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    user = await db_user(message.from_user)
    if not user.language:
        await ask_language(message)
    else:
        await show_menu(message, user.language, "welcome")


@router.message(Command("stats"))
async def stats_cmd(message: Message, state: FSMContext):
    """Faqat admin chatda: foydalanuvchilar statistikasi."""
    if not settings.ADMIN_CHAT_ID or str(message.chat.id) != str(settings.ADMIN_CHAT_ID):
        return await menu_cmd(message, state)
    from .dashboard import user_stats

    s = await sync_to_async(user_stats)()
    await message.answer(
        "📊 <b>Bot statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{s['total']}</b>\n"
        f"🆕 Bugun: <b>{s['today']}</b>\n"
        f"📅 Oxirgi 7 kun: <b>{s['week']}</b>\n"
        f"🗓 Oxirgi 30 kun: <b>{s['month']}</b>\n\n"
        f"📱 Raqami borlar: <b>{s['with_phone']}</b>\n"
        f"📝 Ariza topshirganlar: <b>{s['applied']}</b>\n"
        f"🇺🇿 O'zbekcha: {s['uz']}   🇷🇺 Ruscha: {s['ru']}   ❔ Til tanlamagan: {s['no_lang']}",
        parse_mode="HTML",
    )


@router.message(Command("menu"))
async def menu_cmd(message: Message, state: FSMContext):
    await state.clear()
    user = await db_user(message.from_user)
    if not user.language:
        return await ask_language(message)
    await show_menu(message, user.language)


@router.callback_query(F.data.startswith("lang:"))
async def set_language(call: CallbackQuery, state: FSMContext):
    lang = call.data.split(":")[1]
    if lang not in LANGS:
        return await call.answer()
    user = await db_user(call.from_user)
    first_time = not user.language
    await db_set_lang(call.from_user.id, lang)
    await state.clear()
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass
    await show_menu(call.message, lang, "welcome" if first_time else "language_changed")
    await call.answer()


async def show_section(message: Message, pk, lang):
    sec, path, items = await db_section(pk)
    if not sec:
        return await show_menu(message, lang)
    kb = None
    if items:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i.title(lang), callback_data=f"item:{i.pk}")] for i in items
        ])
    await deliver(message.bot, message.chat.id, sec.content(lang) or sec.title(lang), path, reply_markup=kb)


@router.callback_query(F.data.startswith("sec:"))
async def section_back(call: CallbackQuery):
    user = await db_user(call.from_user)
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass
    await show_section(call.message, int(call.data.split(":")[1]), user.language or "uz")
    await call.answer()


@router.callback_query(F.data.startswith("item:"))
async def section_item(call: CallbackQuery):
    user = await db_user(call.from_user)
    lang = user.language or "uz"
    item, path = await db_item(int(call.data.split(":")[1]))
    if not item:
        return await call.answer("❌", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await db_text("back_btn", lang), callback_data=f"sec:{item.section_id}")]
    ])
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass
    await deliver(call.bot, call.message.chat.id, item.content(lang) or item.title(lang), path, reply_markup=kb)
    await call.answer()


async def vacancies_list(message: Message, lang):
    """Avval joy tanlanadi (joylar bo'lsa), so'ng shu joyning vakansiyalari."""
    locs = await db_locations()
    if not locs:
        return await show_vacancies(message, lang, None)
    rows = [[InlineKeyboardButton(text=f"📍 {loc.name(lang)} ({loc.n})", callback_data=f"loc:{loc.pk}")] for loc in locs]
    rows.append([InlineKeyboardButton(text=await db_text("all_locations", lang), callback_data="loc:all")])
    await send(message, await db_text("choose_location", lang), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def show_vacancies(message: Message, lang, loc_key):
    """loc_key: joy id (str), "all" yoki None (joylar umuman yo'q)."""
    loc = await db_location(int(loc_key)) if loc_key and loc_key != "all" else None
    vacs = await db_vacancies(loc.pk if loc else None)
    back = [InlineKeyboardButton(text=await db_text("back_btn", lang), callback_data="vacs")] if loc_key else None
    if not vacs:
        kb = InlineKeyboardMarkup(inline_keyboard=[back]) if back else None
        return await send(message, await db_text("no_vacancies", lang), reply_markup=kb)
    suffix = f":{loc_key}" if loc_key else ""
    rows = [[InlineKeyboardButton(text=v.title(lang), callback_data=f"vac:{v.pk}{suffix}")] for v in vacs]
    if back:
        rows.append(back)
    title = await db_text("vacancies_title", lang)
    if loc:
        title = f"📍 {loc.name(lang)}\n\n{title}"
    await send(message, title, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def _replace(call: CallbackQuery):
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "vacs")
async def back_to_vacancies(call: CallbackQuery):
    user = await db_user(call.from_user)
    await _replace(call)
    await vacancies_list(call.message, user.language or "uz")
    await call.answer()


@router.callback_query(F.data.startswith("loc:"))
async def location_vacancies(call: CallbackQuery):
    user = await db_user(call.from_user)
    await _replace(call)
    await show_vacancies(call.message, user.language or "uz", call.data.split(":")[1])
    await call.answer()


@router.callback_query(F.data.startswith("vac:"))
async def vacancy_detail(call: CallbackQuery):
    user = await db_user(call.from_user)
    lang = user.language or "uz"
    parts = call.data.split(":")  # vac:<id> yoki vac:<id>:<joy>
    vac = await db_vacancy(int(parts[1]))
    if not vac:
        return await call.answer("❌", show_alert=True)
    text = f"💼 <b>{escape(vac.title(lang))}</b>\n"
    if vac.description(lang):
        text += f"\n{escape(vac.description(lang))}\n"
    if vac.location:
        text += f"\n🏢 {escape(await db_text('location_label', lang))}: {escape(vac.location.name(lang))}"
    if vac.full_address():
        addr = escape(vac.full_address())
        if vac.location and vac.location.map_url:
            addr = f'<a href="{escape(vac.location.map_url)}">{addr}</a>'
        text += f"\n📍 {escape(await db_text('address_label', lang))}: {addr}"
    back = f"loc:{parts[2]}" if len(parts) > 2 else "vacs"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await db_text("apply_btn", lang), callback_data=f"apply:{vac.pk}")],
        [InlineKeyboardButton(text=await db_text("back_btn", lang), callback_data=back)],
    ])
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass
    await call.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


# ---- ariza topshirish (FSM)
async def cancel_kb(lang):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=await db_text("cancel_btn", lang))]], resize_keyboard=True
    )


@router.callback_query(F.data.startswith("apply:"))
async def apply_start(call: CallbackQuery, state: FSMContext):
    user = await db_user(call.from_user)
    lang = user.language or "uz"
    await state.set_state(Apply.name)
    await state.update_data(vacancy_id=int(call.data.split(":")[1]))
    await send(call.message, await db_text("ask_name", lang), reply_markup=await cancel_kb(lang))
    await call.answer()


async def maybe_cancel(message: Message, state: FSMContext, lang) -> bool:
    if message.text and message.text in await db_labels("cancel_btn"):
        await state.clear()
        await show_menu(message, lang, "cancelled")
        return True
    return False


@router.message(Apply.name, F.text)
async def apply_name(message: Message, state: FSMContext):
    user = await db_user(message.from_user)
    lang = user.language or "uz"
    if await maybe_cancel(message, state, lang):
        return
    await state.update_data(full_name=message.text.strip()[:255])
    await state.set_state(Apply.phone)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=await db_text("send_phone_btn", lang), request_contact=True)],
            [KeyboardButton(text=await db_text("cancel_btn", lang))],
        ],
        resize_keyboard=True,
    )
    await send(message, await db_text("ask_phone", lang), reply_markup=kb)


def clean_phone(raw):
    digits = re.sub(r"\D", "", raw or "")
    if not 9 <= len(digits) <= 15:
        return None
    return "+" + digits if len(digits) > 9 else digits


@router.message(Apply.phone)
async def apply_phone(message: Message, state: FSMContext):
    user = await db_user(message.from_user)
    lang = user.language or "uz"
    if await maybe_cancel(message, state, lang):
        return
    phone = clean_phone(message.contact.phone_number if message.contact else message.text)
    if not phone:
        return await send(message, await db_text("invalid_phone", lang))
    data = await state.get_data()
    questions = await db_questions(data.get("vacancy_id"))
    await state.update_data(phone=phone, q_ids=[q.pk for q in questions], idx=0, answers=[])
    await next_question(message, state, user, lang)


async def ask_question(message: Message, lang, q: Question):
    rows = []
    if q.answer_type == "choice":
        opts = q.options(lang)
        for i in range(0, len(opts), 2):
            rows.append([KeyboardButton(text=o) for o in opts[i:i + 2]])
    elif q.answer_type == "phone":
        rows.append([KeyboardButton(text=await db_text("send_phone_btn", lang), request_contact=True)])
    if not q.is_required:
        rows.append([KeyboardButton(text=await db_text("skip_btn", lang))])
    rows.append([KeyboardButton(text=await db_text("cancel_btn", lang))])
    await send(message, q.text(lang), reply_markup=ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True))


async def next_question(message: Message, state: FSMContext, user, lang):
    data = await state.get_data()
    ids, idx = data.get("q_ids", []), data.get("idx", 0)
    while idx < len(ids):
        q = await db_question(ids[idx])
        if q:
            await state.update_data(idx=idx)
            await state.set_state(Apply.question)
            return await ask_question(message, lang, q)
        idx += 1
    await finish_application(message, state, user, lang)


async def finish_application(message: Message, state: FSMContext, user, lang):
    data = await state.get_data()
    await state.clear()
    answers = data.get("answers", [])
    app = await db_save_application(user, data.get("vacancy_id"), data.get("full_name", ""), data["phone"], answers)
    await show_menu(message, lang, "applied")
    await notify_admin(message.bot, app, answers)


@router.message(Apply.question)
async def apply_question(message: Message, state: FSMContext):
    user = await db_user(message.from_user)
    lang = user.language or "uz"
    if await maybe_cancel(message, state, lang):
        return
    data = await state.get_data()
    idx = data.get("idx", 0)
    q = await db_question(data["q_ids"][idx])
    answers = data.get("answers", [])
    text = (message.text or message.caption or "").strip()

    if q:
        skipped = (not q.is_required) and text in await db_labels("skip_btn")
        if not skipped:
            if q.answer_type == "file":
                f = incoming_file(message)
                if not f:
                    return await send(message, await db_text("invalid_file", lang))
                file_id, name, size = f
                if size > MAX_FILE:
                    return await send(message, await db_text("file_too_big", lang))
                saved = await save_tg_file(message.bot, file_id, name, "answers")
                answers.append([q.text("uz"), text or "Fayl yuborildi", saved])
                await state.update_data(idx=idx + 1, answers=answers)
                return await next_question(message, state, user, lang)
            if q.answer_type == "phone":
                value = clean_phone(message.contact.phone_number if message.contact else text)
                if not value:
                    return await send(message, await db_text("invalid_phone", lang))
            elif q.answer_type == "number":
                if not text.replace(" ", "").isdigit():
                    return await send(message, await db_text("invalid_number", lang))
                value = text
            elif q.answer_type == "choice":
                if text not in q.options(lang):
                    return await send(message, await db_text("invalid_choice", lang))
                value = text
            else:
                if not text:
                    return await ask_question(message, lang, q)
                value = text
            answers.append([q.text("uz"), value])
    await state.update_data(idx=idx + 1, answers=answers)
    await next_question(message, state, user, lang)


async def notify_admin(bot: Bot, app: Application, answers):
    if not settings.ADMIN_CHAT_ID:
        return
    text = (
        "🆕 <b>Yangi ariza</b>\n\n"
        f"💼 {escape(app.vacancy_title)}\n👤 {escape(app.full_name)}\n📱 {escape(app.phone)}"
    )
    files = []
    for q, a, *rest in answers:
        text += f"\n\n❓ {escape(q)}\n➡️ {escape(a)}" + (" 📎" if rest else "")
        if rest:
            files.append((q, rest[0]))
    try:
        await bot.send_message(settings.ADMIN_CHAT_ID, text, parse_mode="HTML")
        for q, name in files:  # rezyume va boshqa fayllarni ham admin chatga yuboramiz
            path = await sync_to_async(lambda n=name: file_path(Answer(file=n).file))()
            await deliver(bot, settings.ADMIN_CHAT_ID, f"📎 {app.full_name} — {q}", path)
    except Exception as e:  # noqa
        log.warning("Admin xabari yuborilmadi: %s", e)


# ---- asosiy menyu tugmalari (matn bo'yicha)
@router.message(StateFilter(None), F.text)
async def text_router(message: Message):
    user = await db_user(message.from_user)
    if not user.language:
        return await ask_language(message)
    lang = user.language
    text = message.text

    if text in await db_labels("menu_vacancies"):
        return await vacancies_list(message, lang)
    if text in await db_labels("menu_language"):
        return await ask_language(message)
    for s in await db_sections():
        if text in (s.title_uz, s.title_ru):
            return await show_section(message, s.pk, lang)
    # menyuga tegishli bo'lmagan matn — adminga yozilgan xabar sifatida saqlaymiz
    await db_save_incoming(user, text)
    await show_menu(message, lang, "message_received")
    await notify_admin_incoming(message.bot, user, text)


@router.message(StateFilter(None), F.photo | F.document)
async def file_router(message: Message):
    """Foydalanuvchi menyudan tashqarida yuborgan rasm/fayl — adminga xabar sifatida saqlanadi."""
    user = await db_user(message.from_user)
    if not user.language:
        return await ask_language(message)
    file_id, name, size = incoming_file(message)
    if size > MAX_FILE:
        return await send(message, await db_text("file_too_big", user.language))
    saved = await save_tg_file(message.bot, file_id, name, "messages")
    caption = (message.caption or "").strip()
    await db_save_incoming(user, caption, saved)
    await show_menu(message, user.language, "message_received")
    await notify_admin_incoming(message.bot, user, caption or "📎 Fayl yubordi", copy_from=message)


async def notify_admin_incoming(bot: Bot, user: TelegramUser, text, copy_from: Message = None):
    if not settings.ADMIN_CHAT_ID:
        return
    name = escape(user.full_name or str(user.tg_id)) + (f" (@{escape(user.username)})" if user.username else "")
    try:
        await bot.send_message(
            settings.ADMIN_CHAT_ID, f"📩 <b>Foydalanuvchidan xabar</b>\n👤 {name}\n\n{escape(text)}", parse_mode="HTML",
        )
        if copy_from:
            await bot.copy_message(settings.ADMIN_CHAT_ID, copy_from.chat.id, copy_from.message_id)
    except Exception as e:  # noqa
        log.warning("Admin xabari yuborilmadi: %s", e)


async def reminder_loop():
    """Polling rejimida har 10 daqiqada suhbat eslatmalarini tekshiradi."""
    from .notify import send_due_reminders

    while True:
        try:
            n = await sync_to_async(send_due_reminders, thread_sensitive=False)()
            if n:
                log.info("Suhbat eslatmasi yuborildi: %s", n)
        except Exception:  # noqa
            log.exception("Eslatmalarni yuborishda xato")
        await asyncio.sleep(600)


# ---------------------------------------------------------------- run
_dispatcher = None


def get_dispatcher():
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = Dispatcher(storage=DBStorage())
        _dispatcher.include_router(router)
    return _dispatcher


async def process_update(data):
    """Webhook orqali kelgan bitta yangilanishni qayta ishlaydi."""
    bot = make_bot()
    try:
        await get_dispatcher().feed_webhook_update(bot, data)
    finally:
        await bot.session.close()


async def set_webhook(url):
    bot = make_bot()
    try:
        await bot.set_webhook(
            url, secret_token=settings.WEBHOOK_SECRET,
            allowed_updates=get_dispatcher().resolve_used_update_types(),
        )
        return await bot.get_webhook_info()
    finally:
        await bot.session.close()


async def main():
    token = settings.BOT_TOKEN
    if not token:
        raise SystemExit("BOT_TOKEN topilmadi. .env faylga tokenni yozing.")
    await sync_to_async(ensure_texts)()
    bot = make_bot()
    dp = get_dispatcher()
    reminders = asyncio.create_task(reminder_loop())  # noqa: F841 — polling davomida ishlaydi
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    log.info("Bot ishga tushdi: @%s", me.username)
    await dp.start_polling(bot)


def run():
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
