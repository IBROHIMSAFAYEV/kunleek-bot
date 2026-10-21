#!/usr/bin/env bash
# Ubuntu/Debian serverga bir buyruq bilan o'rnatish (VPS: Hetzner, DigitalOcean, mahalliy hosting...).
#   sudo bash deploy/setup_ubuntu.sh
# Natija: admin panel (gunicorn + nginx, 80-port) va Telegram bot — ikkalasi systemd xizmati,
# server qayta yoqilsa o'zi ishga tushadi, xato bo'lsa o'zi qayta yoqiladi.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_USER="${SUDO_USER:-$(whoami)}"
cd "$APP_DIR"

echo "==> 1/6 Tizim paketlari"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip nginx

echo "==> 2/6 Python muhiti va kutubxonalar"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "==> 3/6 .env tekshiruvi"
if [ ! -f .env ]; then
  cp .env.example .env
  SECRET=$(./venv/bin/python -c "import secrets; print(secrets.token_urlsafe(50))")
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|" .env
  IP=$(hostname -I | awk '{print $1}')
  sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=127.0.0.1,localhost,${IP}|" .env
  echo "!!! .env yaratildi. BOT_TOKEN, ADMIN_CHAT_ID va ADMIN_PASSWORD ni yozing:  nano $APP_DIR/.env"
  echo "!!! So'ng skriptni qayta ishga tushiring."
  exit 1
fi
grep -q '^BOT_TOKEN=.\+' .env || { echo "!!! .env da BOT_TOKEN bo'sh"; exit 1; }

echo "==> 4/6 Baza, statik fayllar, admin"
./venv/bin/python manage.py migrate --noinput
./venv/bin/python manage.py collectstatic --noinput
./venv/bin/python manage.py ensure_admin
./venv/bin/python manage.py check --deploy || true
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "==> 5/6 systemd xizmatlari"
cat > /etc/systemd/system/kunleek-web.service <<EOF
[Unit]
Description=Kunleek HR admin panel (gunicorn)
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/kunleek-bot.service <<EOF
[Unit]
Description=Kunleek HR Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python manage.py runbot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "==> 6/6 nginx (80-port -> admin panel)"
cat > /etc/nginx/sites-available/kunleek <<EOF
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 50M;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/kunleek /etc/nginx/sites-enabled/kunleek
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

systemctl daemon-reload
systemctl enable --now kunleek-web kunleek-bot
sleep 3
systemctl --no-pager --lines=3 status kunleek-web kunleek-bot || true

echo
echo "✅ Tayyor. Admin panel: http://$(hostname -I | awk '{print $1}')/"
echo "   Loglar:  journalctl -u kunleek-bot -f    |    journalctl -u kunleek-web -f"
echo "   Yangilash: kodni almashtirib  sudo bash deploy/setup_ubuntu.sh  ni qayta ishga tushiring."
