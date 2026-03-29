# Claude Code — Setup Guide

Полный список команд для настройки Claude Code на чистом VPS (Ubuntu).
Замени плейсхолдеры вида `YOUR_...` на свои значения.

---

## Содержание

1. [Базовая настройка VPS](#1-базовая-настройка-vps)
2. [Установка Claude Code](#2-установка-claude-code)
3. [Память и логи сессий](#3-память-и-логи-сессий)
4. [Telegram бот для общения с Claude](#4-telegram-бот-для-общения-с-claude)
5. [Просмотр фото через Telegram](#5-просмотр-фото-через-telegram)
6. [Веб-терминал через браузер (Safari/Chrome)](#6-веб-терминал-через-браузер-safarichrome)
7. [Веб-чат с Claude через сайт](#7-веб-чат-с-claude-через-сайт)
8. [Nginx — настройка роутинга](#8-nginx--настройка-роутинга)
9. [HTTPS — самоподписанный сертификат](#9-https--самоподписанный-сертификат)

---

## 1. Базовая настройка VPS

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Создание пользователя с sudo
sudo adduser YOUR_USERNAME
sudo usermod -aG sudo YOUR_USERNAME

# Настройка UFW файрвола
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status

# Отключить root SSH login
sudo nano /etc/ssh/sshd_config
# Найди: PermitRootLogin yes → изменить на: PermitRootLogin no
sudo systemctl restart ssh

# Установить fail2ban
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 2. Установка Claude Code

```bash
# Установить Node.js (если не установлен)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Установить Claude Code
npm install -g @anthropic-ai/claude-code

# Авторизация
claude auth

# Проверить версию
claude --version

# Запустить в режиме без подтверждений (для ботов)
claude -p --dangerously-skip-permissions "твой запрос"
```

---

## 3. Память и логи сессий

Система позволяет Claude помнить контекст между сессиями.

```bash
# Создать директорию для логов
mkdir -p ~/claude_logs/photos

# Разрешить Claude читать папку логов (в settings.json)
nano ~/.claude/settings.json
```

Добавить в `settings.json`:
```json
{
  "env": {},
  "additionalDirectories": [
    "/home/YOUR_USERNAME/claude_logs"
  ]
}
```

Структура логов:
```
~/claude_logs/
├── shared_history.json     # общая история всех разговоров
├── photos/                 # фото из Telegram
├── session_YYYYMMDD.log    # логи сессий
└── live_current.md         # текущая активная сессия
```

Добавить в `~/CLAUDE.md` (инструкция для каждой сессии):
```markdown
## Инструкция для новой сессии
В начале каждой сессии:
1. Прочитай `~/claude_logs/shared_history.json`
2. Прочитай свежие файлы из `~/claude_logs/`
3. Восстанови контекст и спроси с чего продолжаем
```

---

## 4. Telegram бот для общения с Claude

### Требования
```bash
# Создать виртуальное окружение Python
python3 -m venv ~/tgbot
cd ~/tgbot
source bin/activate

# Установить зависимости
pip install python-telegram-bot
```

### Основной файл `~/tgbot/bot.py`
```python
import subprocess
import os
import json
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # получить у @BotFather
HISTORY_FILE = '/home/YOUR_USERNAME/claude_logs/shared_history.json'
PHOTOS_DIR = '/home/YOUR_USERNAME/claude_logs/photos'

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def build_prompt(history, user_msg):
    lines = []
    for entry in history[-20:]:
        source = entry.get('source', 'unknown')
        lines.append(f"Human ({source}): {entry['user']}")
        lines.append(f"Assistant: {entry['assistant']}")
    lines.append(f"Human (telegram): {user_msg}")
    return '\n'.join(lines)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'{PHOTOS_DIR}/photo_{timestamp}.jpg'
    await file.download_to_drive(filename)
    caption = update.message.caption or ''
    await update.message.reply_text(f"Фото сохранено: {filename}")
    history = load_history()
    history.append({
        'source': 'telegram',
        'time': datetime.now().isoformat(),
        'user': f'[ФОТО сохранено: {filename}] {caption}',
        'assistant': 'Фото получено и сохранено на сервер.'
    })
    save_history(history)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text("Думаю...")
    history = load_history()
    prompt = build_prompt(history, user_text)
    result = subprocess.run(
        ['claude', '-p', '--dangerously-skip-permissions', prompt],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, 'HOME': '/home/YOUR_USERNAME', 'USER': 'YOUR_USERNAME'}
    )
    reply = result.stdout.strip() or result.stderr.strip() or 'Нет ответа'
    history.append({
        'source': 'telegram',
        'time': datetime.now().isoformat(),
        'user': user_text,
        'assistant': reply
    })
    save_history(history)
    await update.message.reply_text(reply)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
```

### Systemd сервис `~/tgbot/tgbot.service`
```ini
[Unit]
Description=Telegram Claude Bot
After=network.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/tgbot
ExecStart=/home/YOUR_USERNAME/tgbot/bin/python3 /home/YOUR_USERNAME/tgbot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Установить и запустить сервис
sudo cp ~/tgbot/tgbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tgbot
sudo systemctl start tgbot

# Проверить статус
sudo systemctl status tgbot

# Логи в реальном времени
sudo journalctl -u tgbot -f
```

---

## 5. Просмотр фото через Telegram

Бот автоматически сохраняет фото в `~/claude_logs/photos/`.
Чтобы Claude увидел фото в консоли:

```bash
# Посмотреть последнее сохранённое фото
ls -lt ~/claude_logs/photos/ | head -5

# Claude может прочитать его в сессии:
# "посмотри последнее фото из ~/claude_logs/photos/"
```

Для автоматического чтения фото — добавить в `CLAUDE.md`:
```markdown
Если пользователь упоминает фото — проверь ~/claude_logs/photos/
и прочитай последний файл с помощью Read tool.
```

---

## 6. Веб-терминал через браузер (Safari/Chrome)

Позволяет открыть полноценный терминал прямо в браузере.

```bash
# Установить ttyd
sudo apt install ttyd -y

# Или вручную (последняя версия):
wget https://github.com/tsl0922/ttyd/releases/latest/download/ttyd.x86_64 -O /usr/bin/ttyd
sudo chmod +x /usr/bin/ttyd
```

Сервис `/etc/systemd/system/ttyd.service`:
```ini
[Unit]
Description=ttyd Web Terminal
After=network.target

[Service]
User=YOUR_USERNAME
ExecStart=/usr/bin/ttyd --writable -p 7681 bash
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable ttyd
sudo systemctl start ttyd
```

Nginx маршрут (в `/etc/nginx/sites-enabled/default`):
```nginx
location /terminal {
    proxy_pass http://127.0.0.1:7681/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600;
    proxy_buffering off;
}
```

Открыть: `https://YOUR_DOMAIN/terminal`

---

## 7. Веб-чат с Claude через сайт

Flask-приложение для общения с Claude через веб-интерфейс.

```bash
# Установить Flask
~/tgbot/bin/pip install flask

# Создать директорию
mkdir -p ~/webchat
```

Сервис `/etc/systemd/system/webchat.service`:
```ini
[Unit]
Description=AI Web Chat
After=network.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/webchat
ExecStart=/home/YOUR_USERNAME/tgbot/bin/python3 /home/YOUR_USERNAME/webchat/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable webchat
sudo systemctl start webchat
```

Nginx маршрут:
```nginx
location /webchat {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

---

## 8. Nginx — настройка роутинга

```bash
# Установить nginx
sudo apt install nginx -y

# Основной конфиг
sudo nano /etc/nginx/sites-enabled/default
```

Шаблон конфига для всего в одном:
```nginx
server {
    listen 443 ssl;
    server_name YOUR_DOMAIN;

    ssl_certificate /etc/ssl/certs/YOUR_DOMAIN.crt;
    ssl_certificate_key /etc/ssl/private/YOUR_DOMAIN.key;

    # Статический сайт
    root /home/YOUR_USERNAME/YOUR_SITE_DIR;
    index index.html;
    location / {
        try_files $uri $uri/ =404;
    }

    # Веб-чат
    location /webchat {
        proxy_pass http://127.0.0.1:8080;
    }

    # Терминал
    location /terminal {
        proxy_pass http://127.0.0.1:7681/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600;
        proxy_buffering off;
    }
}
```

```bash
# Проверить конфиг и перезапустить
sudo nginx -t
sudo systemctl reload nginx
```

---

## 9. HTTPS — самоподписанный сертификат

```bash
# Сгенерировать сертификат
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/YOUR_DOMAIN.key \
  -out /etc/ssl/certs/YOUR_DOMAIN.crt \
  -subj "/CN=YOUR_DOMAIN"

# Или использовать Let's Encrypt (для реального домена)
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d YOUR_DOMAIN
```

---

## Полезные команды

```bash
# Статус всех сервисов
sudo systemctl status tgbot webchat ttyd nginx

# Перезапустить все
sudo systemctl restart tgbot webchat ttyd nginx

# Логи в реальном времени
sudo journalctl -u tgbot -f
sudo journalctl -u webchat -f

# Посмотреть историю разговоров
cat ~/claude_logs/shared_history.json | python3 -m json.tool | tail -50

# Посмотреть последние фото
ls -lt ~/claude_logs/photos/
```

---

*Обновлено: 2026-03-29*
