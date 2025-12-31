# iplist Telegram Bot

Бот для автоматического добавления сайтов в репозиторий [iplist](https://github.com/ckeiituk/iplist).

## Возможности

- 🤖 Автоматическая классификация домена через AI (AgentRouter)
- 🔍 DNS резолвинг (A/AAAA записи)
- 📤 Создание файла в GitHub репозитории

## Установка

```bash
cd iplist-bot
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

## Настройка

Создай файл `.env`:

```bash
TG_TOKEN=токен_от_BotFather
GITHUB_TOKEN=github_personal_access_token
AGENTROUTER_KEY=ключ_agentrouter
```

## Запуск

```bash
# Вариант 1: прямой запуск
source .venv/bin/activate
export $(cat .env | xargs)
python bot.py

# Вариант 2: с python-dotenv (добавь в requirements.txt)
python bot.py
```

## Использование

1. Напиши `/start` боту
2. Отправь домен, например: `greasyfork.org`
3. Бот определит категорию, получит IP и создаст файл в репозитории

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
