# iplist Telegram Bot

Бот для автоматического добавления сайтов в репозиторий [iplist](https://github.com/ckeiituk/iplist).

## Возможности

- 🤖 Автоматическая классификация домена через AI (Google Gemini)
- 🔍 DNS резолвинг (A/AAAA записи)
- 📤 Создание файла в GitHub репозитории

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
```

## Команды

- Отправь домен → автоматическая категоризация через AI
- `/add <домен> <категория>` → ручной выбор категории
- `/categories` → список доступных категорий

## Формат JSON

```json
{
    "domains": ["domain.com", "www.domain.com"],
    "dns": ["127.0.0.11:53", "77.88.8.88:53", "8.8.8.8:53", "1.1.1.1:53"],
    "timeout": 3600,
    "ip4": ["1.2.3.4"],
    "ip6": ["2a06:..."],
    "cidr4": [],
    "cidr6": [],
    "external": { "domains": [], "ip4": [], "ip6": [], "cidr4": [], "cidr6": [] }
}
```
