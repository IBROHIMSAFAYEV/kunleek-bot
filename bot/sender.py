"""Telegramga oddiy matn va rasm/fayl yuborish (bot ham, admin panel ham shu yerdan foydalanadi)."""
import asyncio
from pathlib import Path

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile
from django.conf import settings

from .models import file_path

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
TEXT_LIMIT, CAPTION_LIMIT = 4096, 1024


def make_bot():
    """Bot obyekti; TELEGRAM_PROXY berilgan bo'lsa (PythonAnywhere bepul tarifi), proksi orqali ulanadi."""
    session = AiohttpSession(proxy=settings.TELEGRAM_PROXY) if settings.TELEGRAM_PROXY else None
    return Bot(settings.BOT_TOKEN, session=session)


async def deliver(bot: Bot, chat_id, text="", path=None, reply_markup=None):
    """Matnni (uzun bo'lsa bo'lib) va ixtiyoriy faylni yuboradi. Tugmalar oxirgi xabarga qo'yiladi."""
    text = (text or "").strip()
    chunks = [text[i:i + TEXT_LIMIT] for i in range(0, len(text), TEXT_LIMIT)]
    if path:
        caption = chunks.pop(0) if len(chunks) == 1 and len(chunks[0]) <= CAPTION_LIMIT else None
        kw = {"caption": caption, "parse_mode": None, "reply_markup": None if chunks else reply_markup}
        if Path(path).suffix.lower() in IMAGE_EXT:
            try:
                await bot.send_photo(chat_id, FSInputFile(path), **kw)
            except TelegramBadRequest:  # juda katta yoki noto'g'ri rasm — fayl qilib yuboramiz
                await bot.send_document(chat_id, FSInputFile(path), **kw)
        else:
            await bot.send_document(chat_id, FSInputFile(path), **kw)
    for i, chunk in enumerate(chunks):
        last = i == len(chunks) - 1
        await bot.send_message(chat_id, chunk, parse_mode=None, reply_markup=reply_markup if last else None)


def send_announcement(ann, by=None):
    """E'lonni barcha qabul qiluvchilarga o'z tilida yuboradi va natijani e'longa yozadi."""
    from django.utils import timezone

    path = file_path(ann.file)
    jobs = [(tg_id, ann.text(lang)) for tg_id, lang in ann.recipients().values_list("tg_id", "language")]
    sent = failed = 0

    async def run():
        nonlocal sent, failed
        bot = make_bot()
        try:
            for chat_id, text in jobs:
                try:
                    await deliver(bot, chat_id, text, path)
                    sent += 1
                except Exception:  # noqa — bloklagan/o'chirilgan akkauntlar
                    failed += 1
                await asyncio.sleep(0.05)  # Telegram limitlaridan oshmaslik uchun
        finally:
            await bot.session.close()

    if settings.BOT_TOKEN and jobs:
        asyncio.run(run())
    else:
        failed = len(jobs)
    ann.sent_count, ann.failed_count = sent, failed
    ann.status, ann.sent_at, ann.sent_by = "sent", timezone.now(), by
    ann.save(update_fields=["sent_count", "failed_count", "status", "sent_at", "sent_by"])
    return sent, failed


def send_messages(messages):
    """Admin paneldan DirectMessage'larni yuboradi va holatini yozadi. (yuborildi, xato) sonini qaytaradi."""

    # bazadan o'qishni async ichida qilib bo'lmaydi, shuning uchun oldindan tayyorlaymiz
    jobs = [(m, m.user.tg_id, file_path(m.file)) for m in messages]

    async def run():
        bot = make_bot()
        try:
            for m, chat_id, path in jobs:
                try:
                    await deliver(bot, chat_id, m.text, path)
                    m.status, m.error = "sent", ""
                except Exception as e:  # noqa — har qanday xatoni adminga ko'rsatamiz
                    m.status, m.error = "error", str(e)
                await asyncio.sleep(0.05)  # Telegram limitlaridan oshmaslik uchun
        finally:
            await bot.session.close()

    if not settings.BOT_TOKEN:
        for m in messages:
            m.status, m.error = "error", "BOT_TOKEN topilmadi"
    else:
        asyncio.run(run())
    for m in messages:
        m.save(update_fields=["status", "error"])
    ok = sum(m.status == "sent" for m in messages)
    return ok, len(messages) - ok
