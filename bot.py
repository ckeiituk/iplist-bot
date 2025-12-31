#!/usr/bin/env python3
"""
Telegram bot for automating site additions to iplist GitHub repository.
"""

import os
import json
import base64
import logging
import dns.resolver
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TG_TOKEN = os.getenv("TG_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
AGENTROUTER_KEY = os.getenv("AGENTROUTER_KEY")

# Constants
GITHUB_REPO = "ckeiituk/iplist"
GITHUB_BRANCH = "master"
AGENTROUTER_BASE_URL = "https://api.agentrouter.org/v1"
AGENTROUTER_MODEL = "deepseek-v3.2"

DNS_SERVERS = ["127.0.0.11:53", "77.88.8.88:53", "8.8.8.8:53", "1.1.1.1:53"]


async def get_categories_from_github() -> list[str]:
    """Get list of category folders from GitHub repo config/ directory."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/config"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
        response.raise_for_status()
        
    contents = response.json()
    categories = [item["name"] for item in contents if item["type"] == "dir"]
    return categories


async def classify_domain(domain: str, categories: list[str]) -> str:
    """Use AgentRouter API to classify domain into a category."""
    url = f"{AGENTROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {AGENTROUTER_KEY}",
        "Content-Type": "application/json"
    }
    
    categories_str = ", ".join(categories)
    prompt = f"Вот список категорий: [{categories_str}]. К какой категории относится сайт {domain}? Верни только название папки."
    
    payload = {
        "model": AGENTROUTER_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 50,
        "temperature": 0.1
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
    result = response.json()
    category = result["choices"][0]["message"]["content"].strip().lower()
    
    # Validate category exists
    if category not in [c.lower() for c in categories]:
        raise ValueError(f"AI вернул неизвестную категорию: {category}")
    
    # Return exact category name from list
    for cat in categories:
        if cat.lower() == category:
            return cat
    
    return category


def resolve_dns(domain: str) -> tuple[list[str], list[str]]:
    """Resolve A and AAAA records for domain."""
    ip4 = []
    ip6 = []
    
    resolver = dns.resolver.Resolver()
    resolver.timeout = 5
    resolver.lifetime = 10
    
    # Resolve A records (IPv4)
    try:
        answers = resolver.resolve(domain, 'A')
        ip4 = [str(rdata) for rdata in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        logger.warning(f"No A records found for {domain}")
    
    # Resolve AAAA records (IPv6)
    try:
        answers = resolver.resolve(domain, 'AAAA')
        ip6 = [str(rdata) for rdata in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        logger.warning(f"No AAAA records found for {domain}")
    
    return ip4, ip6


def create_site_json(domain: str, ip4: list[str], ip6: list[str]) -> dict:
    """Create JSON structure for the site."""
    return {
        "domains": [domain, f"www.{domain}"],
        "dns": DNS_SERVERS,
        "timeout": 3600,
        "ip4": ip4,
        "ip6": ip6,
        "cidr4": [],
        "cidr6": [],
        "external": {
            "domains": [],
            "ip4": [],
            "ip6": [],
            "cidr4": [],
            "cidr6": []
        }
    }


async def create_file_in_github(category: str, domain: str, content: dict) -> str:
    """Create a new file in the GitHub repository."""
    file_path = f"config/{category}/{domain}.json"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Encode content to base64
    json_content = json.dumps(content, indent=4, ensure_ascii=False)
    content_b64 = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": f"Add {domain}",
        "content": content_b64,
        "branch": GITHUB_BRANCH
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.put(url, headers=headers, json=payload)
        response.raise_for_status()
    
    result = response.json()
    return result["content"]["html_url"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "👋 Привет! Я бот для добавления сайтов в iplist.\n\n"
        "Просто отправь мне домен (например: greasyfork.org), и я:\n"
        "1. Определю категорию сайта\n"
        "2. Получу IP адреса через DNS\n"
        "3. Создам файл в репозитории\n\n"
        "📝 Отправляй домен без http:// и www."
    )


async def handle_domain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle domain message from user."""
    domain = update.message.text.strip().lower()
    
    # Basic domain validation
    if not domain or " " in domain or "/" in domain:
        await update.message.reply_text("❌ Неверный формат домена. Отправь домен без http:// и пробелов.")
        return
    
    # Remove common prefixes if present
    domain = domain.replace("https://", "").replace("http://", "").replace("www.", "")
    domain = domain.rstrip("/")
    
    status_msg = await update.message.reply_text(f"⏳ Обрабатываю {domain}...")
    
    try:
        # Step 1: Get categories from GitHub
        await status_msg.edit_text(f"📂 Получаю список категорий...")
        categories = await get_categories_from_github()
        
        if not categories:
            await status_msg.edit_text("❌ Не удалось получить категории из репозитория.")
            return
        
        # Step 2: Classify domain using AI
        await status_msg.edit_text(f"🤖 Определяю категорию для {domain}...")
        category = await classify_domain(domain, categories)
        
        # Step 3: Resolve DNS
        await status_msg.edit_text(f"🔍 Резолвлю DNS для {domain}...")
        ip4, ip6 = resolve_dns(domain)
        
        if not ip4 and not ip6:
            await status_msg.edit_text(f"❌ Не удалось получить IP адреса для {domain}. Домен не резолвится.")
            return
        
        # Step 4: Create JSON
        site_json = create_site_json(domain, ip4, ip6)
        
        # Step 5: Create file in GitHub
        await status_msg.edit_text(f"📤 Создаю файл в репозитории...")
        file_url = await create_file_in_github(category, domain, site_json)
        
        # Success message
        ip_info = []
        if ip4:
            ip_info.append(f"IPv4: {', '.join(ip4)}")
        if ip6:
            ip_info.append(f"IPv6: {', '.join(ip6)}")
        
        await status_msg.edit_text(
            f"✅ Готово!\n\n"
            f"📁 Категория: {category}\n"
            f"🌐 {chr(10).join(ip_info)}\n\n"
            f"🔗 {file_url}"
        )
        
    except httpx.HTTPStatusError as e:
        error_msg = f"❌ Ошибка API: {e.response.status_code}"
        if e.response.status_code == 401:
            error_msg += " (проверь токены)"
        elif e.response.status_code == 404:
            error_msg += " (репозиторий или путь не найден)"
        elif e.response.status_code == 422:
            error_msg += " (файл уже существует?)"
        await status_msg.edit_text(error_msg)
        logger.error(f"HTTP Error: {e}")
        
    except ValueError as e:
        await status_msg.edit_text(f"❌ {str(e)}")
        logger.error(f"Value Error: {e}")
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Непредвиденная ошибка: {type(e).__name__}")
        logger.exception(f"Unexpected error processing {domain}")


def main() -> None:
    """Start the bot."""
    # Validate environment variables
    if not TG_TOKEN:
        raise ValueError("TG_TOKEN environment variable is not set")
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is not set")
    if not AGENTROUTER_KEY:
        raise ValueError("AGENTROUTER_KEY environment variable is not set")
    
    # Create application
    application = Application.builder().token(TG_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_domain))
    
    # Run bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
