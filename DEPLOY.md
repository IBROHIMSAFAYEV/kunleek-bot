# Kunleek HR bot — o'rnatish va serverga joylash

Ichida: Telegram bot (aiogram) + admin panel (Django + Unfold). Baza — SQLite (`db.sqlite3`), yuklangan fayllar — `media/`.

> **Muhim:** bitta bot tokeni bilan bot faqat **bitta joyda** ishlashi kerak. Serverda ishga tushirsangiz, kompyuterdagi botni to'xtating.

---

## 0. Tayyorgarlik (hamma usul uchun)

1. Python **3.10 yoki yangiroq** (sinalgan: 3.12).
2. `.env.example` ni `.env` deb nusxalang va to'ldiring:
   - `BOT_TOKEN` — @BotFather bergan token
   - `ADMIN_CHAT_ID` — yangi arizalar keladigan chat ID
   - `ADMIN_PASSWORD` — admin panelga kirish paroli (login: `ADMIN_USERNAME`, odatda `admin`)
   - `SECRET_KEY` — skriptlar o'zi yaratadi (yoki: `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
   - `ALLOWED_HOSTS` — server IP yoki domen
3. **Eski ma'lumotlar** (vakansiyalar, arizalar, foydalanuvchilar) kerak bo'lsa: `db.sqlite3` va `media/` papkani loyiha papkasiga (yoki `DATA_DIR` ga) ko'chiring. Kerak bo'lmasa — bo'sh baza o'zi yaratiladi.

---

## A. Ubuntu VPS (tavsiya — eng barqaror, 24/7)

```bash
# 1) zipni serverga yuklab oching
unzip "Kunleek bot deploy.zip" && cd kunleek_bot
# 2) bitta buyruq
sudo bash deploy/setup_ubuntu.sh
```
Birinchi marta skript `.env` yaratib to'xtaydi → `nano .env` bilan token va parolni yozing → skriptni **qayta** ishga tushiring.

Natija:
- Admin panel: `http://SERVER_IP/`
- Bot va panel `systemd` xizmati: server qayta yoqilsa o'zi ishlaydi, xato bo'lsa o'zi qayta yoqiladi.
- Loglar: `journalctl -u kunleek-bot -f`, `journalctl -u kunleek-web -f`
- Domen + HTTPS: domenni server IP ga ulang, `sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx`,
  so'ng `.env` da `ALLOWED_HOSTS=domen.uz`, `CSRF_TRUSTED_ORIGINS=https://domen.uz`, `USE_HTTPS=True` va
  `sudo systemctl restart kunleek-web`.

**Yangilash:** yangi kodni ustidan yozing (`.env`, `db.sqlite3`, `media/` ga tegmang) → `sudo bash deploy/setup_ubuntu.sh`.

---

## B. PythonAnywhere (bepul tarif — webhook rejimi)

1. pythonanywhere.com da ro'yxatdan o'ting. **Files** → zipni yuklang. **Consoles → Bash**:
   ```bash
   unzip "Kunleek bot deploy.zip" -d ~ && cd ~/kunleek_bot
   python3.12 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env && nano .env
   ```
   `.env` da qo'shimcha: `ALLOWED_HOSTS=USERNAME.pythonanywhere.com`, `CSRF_TRUSTED_ORIGINS=https://USERNAME.pythonanywhere.com`,
   `TELEGRAM_PROXY=http://proxy.server:3128`, `WEBHOOK_SECRET=` (uzun tasodifiy, faqat harf/raqam/`_`/`-`).
2. ```bash
   python manage.py migrate && python manage.py collectstatic --noinput && python manage.py ensure_admin
   ```
3. **Web** → *Add a new web app* → *Manual configuration* → Python 3.12.
   - *Virtualenv*: `/home/USERNAME/kunleek_bot/venv`
   - *WSGI configuration file*: ichini `deploy/pythonanywhere_wsgi.py` bilan almashtiring (USERNAME ni yozing).
   - *Static files*: URL `/static/` → `/home/USERNAME/kunleek_bot/staticfiles`
   - *Force HTTPS*: yoqing → **Reload**.
4. Botni webhookga ulang (Bash):
   ```bash
   python manage.py setwebhook https://USERNAME.pythonanywhere.com
   ```
5. Suhbat eslatmalari uchun **Tasks** → har kuni 1 marta: `cd ~/kunleek_bot && venv/bin/python manage.py send_reminders`
6. Har 3 oyda **Web** → *Run until 3 months from today* tugmasini bosing (bepul tarif talabi).

> PythonAnywhere da `runbot` ni ishga tushirmang — u webhookni o'chiradi.

---

## C. Railway

1. Kodni GitHub'ga (private) yuklang, railway.app → *New Project* → *Deploy from GitHub*.
2. *Variables*: `.env` dagi qiymatlar + `DATA_DIR=/data`, `DEBUG=False`, `USE_HTTPS=True`.
3. *Volume* qo'shing, mount path: `/data` (baza va fayllar o'chib ketmasligi uchun).
4. *Settings → Networking → Generate Domain*. Domen `ALLOWED_HOSTS`ga avtomatik qo'shiladi.

`railway.json` + `start.sh` bot va admin panelni bitta xizmatda ishga tushiradi.

---

## D. Windows kompyuter (sinash yoki vaqtincha)

```powershell
powershell -ExecutionPolicy Bypass -File setup_windows.ps1
```
Birinchi marta `.env` ochiladi → token/parolni yozing → skriptni qayta ishga tushiring.
Admin panel: http://127.0.0.1:8000/ . Bot va panel fonda ishlaydi va to'xtasa qayta yoqiladi (`run_local.ps1`).

---

## Tekshiruv va muammolar

| Muammo | Yechim |
|---|---|
| Bot javob bermayapti | Token to'g'rimi; bot boshqa joyda (kompyuterda) ham ishlab turmaganmi |
| `TelegramConflictError` | Bitta token bilan ikkita bot ishlayapti — bittasini to'xtating |
| Admin panel "Bad Request (400)" | `.env` dagi `ALLOWED_HOSTS` ga domen/IP yozilmagan |
| Kirishda "CSRF" xatosi | `CSRF_TRUSTED_ORIGINS=https://domen` yozing |
| Dizayn (CSS) chiqmayapti | `python manage.py collectstatic --noinput` |
| Parolni unutdingiz | `python manage.py changepassword admin` |

Foydali buyruqlar: `python manage.py check --deploy` (sozlamalarni tekshiradi), `python manage.py send_reminders`, `python manage.py seed` (namuna ma'lumot).
