"""Bot profilini (nom, tavsif, avatar, buyruqlar) Telegram bilan sinxronlash."""
import asyncio
import io

from aiogram.types import BotCommand, BufferedInputFile, InputProfilePhotoStatic
from django.utils import timezone

from .models import BotProfile, file_path
from .sender import make_bot

# Telegram foydalanuvchi ilovasi tiliga qarab tanlaydi: "" — standart (o'zbekcha), "ru" — ruscha
LANGS = {"": "uz", "ru": "ru"}
COMMANDS = {
    "uz": [("start", "Botni boshlash"), ("menu", "Asosiy menyu")],
    "ru": [("start", "Запустить бота"), ("menu", "Главное меню")],
}



def _square_jpeg(path, size=640):
    from PIL import Image, ImageOps

    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img = ImageOps.fit(img, (size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        return buf.getvalue()


async def _pull():
    bot = make_bot()
    try:
        data = {}
        for code, lang in LANGS.items():
            data[f"name_{lang}"] = (await bot.get_my_name(language_code=code or None)).name
            data[f"short_description_{lang}"] = (await bot.get_my_short_description(language_code=code or None)).short_description
            data[f"description_{lang}"] = (await bot.get_my_description(language_code=code or None)).description
        return data
    finally:
        await bot.session.close()


async def _push(profile, photo_bytes):
    """Faqat o'zgargan qiymatlarni yuboradi (Telegram nom o'zgartirishni kuniga bir necha marta bilan cheklaydi)."""
    bot = make_bot()
    changed = []
    try:
        for code, lang in LANGS.items():
            name = profile.name_uz if lang == "uz" else profile.name_ru
            if (await bot.get_my_name(language_code=code or None)).name != name:
                await bot.set_my_name(name=name, language_code=code or None)
                changed.append(f"nom ({lang})")
            short = profile.short_description_uz if lang == "uz" else profile.short_description_ru
            if (await bot.get_my_short_description(language_code=code or None)).short_description != short:
                await bot.set_my_short_description(short_description=short, language_code=code or None)
                changed.append(f"qisqa tavsif ({lang})")
            desc = profile.description_uz if lang == "uz" else profile.description_ru
            if (await bot.get_my_description(language_code=code or None)).description != desc:
                await bot.set_my_description(description=desc, language_code=code or None)
                changed.append(f"tavsif ({lang})")
            await bot.set_my_commands(
                [BotCommand(command=c, description=d) for c, d in COMMANDS[lang]], language_code=code or None,
            )
        if photo_bytes:
            await bot.set_my_profile_photo(
                photo=InputProfilePhotoStatic(photo=BufferedInputFile(photo_bytes, "avatar.jpg")),
            )
            changed.append("avatar")
        return changed
    finally:
        await bot.session.close()


def pull_from_telegram():
    """Telegramdagi hozirgi nom va tavsiflarni o'qiydi."""
    return asyncio.run(_pull())


def push_to_telegram(profile: BotProfile):
    """Profilni Telegramga yuboradi. (o'zgarganlar ro'yxati, xato matni) qaytaradi."""
    path = file_path(profile.photo)
    new_photo = path and profile.photo.name != profile.photo_synced
    try:
        changed = asyncio.run(_push(profile, _square_jpeg(path) if new_photo else None))
    except Exception as e:  # noqa — xatoni admin sahifasida ko'rsatamiz
        profile.last_error = str(e)
        profile.save(update_fields=["last_error"])
        return [], str(e)
    if new_photo:
        profile.photo_synced = profile.photo.name
    profile.synced_at, profile.last_error = timezone.now(), ""
    profile.save(update_fields=["photo_synced", "synced_at", "last_error"])
    return changed, ""
