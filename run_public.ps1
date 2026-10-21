# Admin panelni Cloudflare tunnel orqali internetga chiqaradi (kompyuter yoqiq turishi kerak).
# Ishga tushirish: powershell -ExecutionPolicy Bypass -File run_public.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$log = Join-Path $env:TEMP "korzinka_tunnel.log"
Remove-Item $log -ErrorAction SilentlyContinue

# 1) tunnel va uning havolasi
$tunnel = Start-Process $cloudflared -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:8080" `
    -RedirectStandardError $log -PassThru -WindowStyle Hidden
$url = $null
for ($i = 0; $i -lt 60 -and -not $url; $i++) {
    Start-Sleep 1
    $m = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value }
}
if (-not $url) { Stop-Process -Id $tunnel.Id; throw "Tunnel havolasi olinmadi, $log ni ko'ring" }

# 2) admin panel: xavfsiz rejimda (DEBUG o'chiq), faqat shu havola uchun
$hostName = ([uri]$url).Host
$env:DEBUG = "False"
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(50))"
$env:ALLOWED_HOSTS = "127.0.0.1,localhost,$hostName"
$env:CSRF_TRUSTED_ORIGINS = $url
python manage.py collectstatic --noinput | Out-Null

Write-Host ""
Write-Host "Admin panel: $url" -ForegroundColor Green
Write-Host "To'xtatish uchun shu oynani yoping yoki Ctrl+C bosing."
try {
    python -m waitress --listen=127.0.0.1:8080 config.wsgi:application
} finally {
    Stop-Process -Id $tunnel.Id -ErrorAction SilentlyContinue
}

