# Windows kompyuterda bir buyruq bilan o'rnatish va ishga tushirish:
#   powershell -ExecutionPolicy Bypass -File setup_windows.ps1
# Python 3.10+ o'rnatilgan bo'lishi kerak (python.org, "Add to PATH" belgisi bilan).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> 1/4 Python muhiti va kutubxonalar"
if (-not (Test-Path venv)) { python -m venv venv }
.\venv\Scripts\python -m pip install --upgrade pip | Out-Null
.\venv\Scripts\pip install -r requirements.txt

Write-Host "==> 2/4 .env tekshiruvi"
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    $secret = .\venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(50))"
    (Get-Content .env) -replace '^SECRET_KEY=.*', "SECRET_KEY=$secret" -replace '^DEBUG=.*', 'DEBUG=True' | Set-Content .env -Encoding utf8
    Write-Host "!!! .env yaratildi. Unga BOT_TOKEN, ADMIN_CHAT_ID va ADMIN_PASSWORD ni yozing (notepad .env), so'ng skriptni qayta ishga tushiring." -ForegroundColor Yellow
    notepad .env
    exit 1
}

Write-Host "==> 3/4 Baza, statik fayllar, admin"
.\venv\Scripts\python manage.py migrate --noinput
.\venv\Scripts\python manage.py collectstatic --noinput | Out-Null
.\venv\Scripts\python manage.py ensure_admin

Write-Host "==> 4/4 Ishga tushirish (bot + admin panel, to'xtasa qayta yoqiladi)"
Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", "$PSScriptRoot\run_local.ps1" -WindowStyle Hidden
Start-Sleep 8
Write-Host "Tayyor: admin panel http://127.0.0.1:8000/  (loglar: logs\ papkasida)" -ForegroundColor Green
Start-Process "http://127.0.0.1:8000/"
