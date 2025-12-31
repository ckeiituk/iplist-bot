# iplist Telegram Bot

Бот для автоматического добавления сайтов в репозиторий [iplist](https://github.com/ckeiituk/iplist).

## Возможности

- 🧠 Умное определение домена (пиши `netflix` → получишь `netflix.com`)
- 🤖 Автоматическая классификация через AI (Google Gemini)
- 🔍 DNS резолвинг (A/AAAA записи)
- 📤 Создание файла в GitHub
- 📊 Отчёты в Telegram канал (опционально)

## Установка

### Docker (рекомендуется)

```bash
git clone https://github.com/ckeiituk/iplist-bot.git
cd iplist-bot
cp env.example .env
nano .env  # заполнить токены
docker compose up -d
```

### Локально

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env && nano .env
python bot.py
```

## Настройка (.env)

```bash
TG_TOKEN=токен_от_BotFather
GITHUB_TOKEN=github_personal_access_token
GEMINI_API_KEY=ключ_от_aistudio.google.com/apikey
LOG_CHANNEL_ID=-1001234567890:14  # опционально, для отчётов
```

## Использование

Просто отправь боту название сервиса или домен:
- `netflix` → автоматически определит `netflix.com`
- `greasyfork.org` → сразу обработает

Бот сам определит категорию, получит IP и создаст файл в репозитории.
