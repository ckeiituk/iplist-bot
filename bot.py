#!/usr/bin/env python3
"""
Telegram bot for automating site additions to iplist GitHub repository.
"""

import os
import json
import base64
import logging
import asyncio
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")  # Optional: channel for reports

# Constants
GITHUB_REPO = "ckeiituk/iplist"
GITHUB_BRANCH = "master"
GEMINI_MODEL = "gemini-2.5-flash-lite"

DNS_SERVERS = ["127.0.0.11:53", "77.88.8.88:53", "8.8.8.8:53", "1.1.1.1:53"]


def debug_test_gemini():
    """Test Gemini API key on startup."""
    import requests
    logger.info(f"DEBUG: Testing Gemini API key (first 10 chars: {GEMINI_API_KEY[:10] if GEMINI_API_KEY else 'NONE'}...)")
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": "hi"}]}],
                "generationConfig": {"maxOutputTokens": 10}
            },
            timeout=10
        )
        logger.info(f"DEBUG Gemini response: {resp.status_code} - {resp.text[:200]}")
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"DEBUG Gemini error: {e}")
        return False

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
    """Use Gemini API to classify domain into a category."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    categories_str = ", ".join(categories)
    prompt = f"Вот список категорий: [{categories_str}]. К какой категории относится сайт {domain}? Ответь ТОЛЬКО названием категории, без пояснений."
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 50,
            "temperature": 0.1
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers={"Content-Type": "application/json"}, json=payload)
        response.raise_for_status()
        
    result = response.json()
    category = result["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
    
    # Validate category exists
    if category not in [c.lower() for c in categories]:
        raise ValueError(f"AI вернул неизвестную категорию: {category}")
    
    # Return exact category name from list
    for cat in categories:
        if cat.lower() == category:
            return cat
    
    return category


async def resolve_domain_from_keyword(keyword: str) -> str:
    """Use Gemini to resolve domain from keyword (e.g. 'netflix' -> 'netflix.com')."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    prompt = (
        f"Какой основной домен у сервиса '{keyword}'? "
        f"Верни ТОЛЬКО домен без http://, www. и пояснений. "
        f"Если не уверен или это не известный сервис, верни 'UNKNOWN'."
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 30,
            "temperature": 0.1
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers={"Content-Type": "application/json"}, json=payload)
        response.raise_for_status()
        
    result = response.json()
    domain = result["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
    
    # Clean up response
    domain = domain.replace("http://", "").replace("https://", "").replace("www.", "").rstrip("/")
    
    if "unknown" in domain or len(domain) > 100 or " " in domain:
        raise ValueError(f"Не удалось определить домен для '{keyword}'")
    
    return domain

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


async def send_log_report(bot, user, domain: str, category: str, ip4: list, ip6: list, file_url: str) -> None:
    """Send a report to the log channel."""
    if not LOG_CHANNEL_ID:
        return
    
    try:
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        user_info = f"@{user.username}" if user.username else f"{user.first_name} (ID: {user.id})"
        
        ip_info = []
        if ip4:
            ip_info.append(f"IPv4: `{', '.join(ip4)}`")
        if ip6:
            ip_info.append(f"IPv6: `{', '.join(ip6[:2])}`")  # Limit IPv6 display
        
        message = (
            f"✅ **Добавлен сайт**\n\n"
            f"🌐 Домен: `{domain}`\n"
            f"📁 Категория: `{category}`\n"
            f"👤 Добавил: {user_info}\n"
            f"🕐 Время: {now}\n"
            f"🔗 [Файл]({file_url})\n\n"
            f"{chr(10).join(ip_info)}"
        )
        
        # Parse channel_id:topic_id format
        chat_id = LOG_CHANNEL_ID
        message_thread_id = None
        if ":" in LOG_CHANNEL_ID:
            parts = LOG_CHANNEL_ID.split(":")
            chat_id = parts[0]
            message_thread_id = int(parts[1])
        
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            message_thread_id=message_thread_id,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Failed to send log report: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "👋 Привет! Я бот для добавления сайтов в iplist.\n\n"
        "Просто отправь мне домен (например: greasyfork.org), и я:\n"
        "1. Определю категорию сайта через AI\n"
        "2. Получу IP адреса через DNS\n"
        "3. Создам файл в репозитории\n\n"
        "📝 Команды:\n"
        "• Отправь домен — автоматическая категоризация\n"
        "• /add <домен> <категория> — указать категорию вручную\n"
        "• /categories — список категорий"
    )


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available categories."""
    try:
        categories = await get_categories_from_github()
        await update.message.reply_text(
            f"📂 Доступные категории:\n\n" + "\n".join(f"• {cat}" for cat in sorted(categories))
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {type(e).__name__}")
        logger.exception("Error fetching categories")


async def add_domain_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add domain with manually specified category."""
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /add <домен> <категория>")
        return
    
    domain = context.args[0].lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
    category = context.args[1].lower()
    
    status_msg = await update.message.reply_text(f"⏳ Обрабатываю {domain}...")
    
    try:
        # Validate category
        categories = await get_categories_from_github()
        matched_cat = None
        for cat in categories:
            if cat.lower() == category:
                matched_cat = cat
                break
        
        if not matched_cat:
            await status_msg.edit_text(
                f"❌ Категория '{category}' не найдена.\n\n"
                f"Доступные: {', '.join(sorted(categories))}"
            )
            return
        
        # Resolve DNS
        await status_msg.edit_text(f"🔍 Резолвлю DNS для {domain}...")
        ip4, ip6 = resolve_dns(domain)
        
        if not ip4 and not ip6:
            await status_msg.edit_text(f"❌ Не удалось получить IP адреса для {domain}.")
            return
        
        # Create JSON and push to GitHub
        site_json = create_site_json(domain, ip4, ip6)
        await status_msg.edit_text(f"📤 Создаю файл в репозитории...")
        file_url = await create_file_in_github(matched_cat, domain, site_json)
        
        ip_info = []
        if ip4:
            ip_info.append(f"IPv4: {', '.join(ip4)}")
        if ip6:
            ip_info.append(f"IPv6: {', '.join(ip6)}")
        
        await status_msg.edit_text(
            f"✅ Готово!\n\n"
            f"📁 Категория: {matched_cat}\n"
            f"🌐 {chr(10).join(ip_info)}\n\n"
            f"🔗 {file_url}"
        )
        
        # Send report to log channel
        await send_log_report(context.bot, update.effective_user, domain, matched_cat, ip4, ip6, file_url)
        
    except httpx.HTTPStatusError as e:
        error_msg = f"❌ Ошибка API: {e.response.status_code}"
        if e.response.status_code == 422:
            error_msg += " (файл уже существует?)"
        await status_msg.edit_text(error_msg)
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {type(e).__name__}")
        logger.exception(f"Error in add_domain_manual")


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
        # Step 0: Smart domain resolution (if needed)
        # Check if it looks like a keyword rather than a domain
        if "." not in domain:
            await status_msg.edit_text(f"🔍 Определяю домен для '{domain}'...")
            try:
                resolved_domain = await resolve_domain_from_keyword(domain)
                await status_msg.edit_text(
                    f"✅ Найден домен: `{resolved_domain}`\n\n"
                    f"Продолжаю обработку..."
                )
                domain = resolved_domain
                await asyncio.sleep(1)  # Give user time to see
            except ValueError as e:
                await status_msg.edit_text(
                    f"❓ {str(e)}\n\n"
                    f"Уточни полный домен или используй /add <домен> <категория>"
                )
                return
        
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
        
        # Send report to log channel
        await send_log_report(context.bot, update.effective_user, domain, category, ip4, ip6, file_url)
        
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
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    
    # Debug test Gemini
    debug_test_gemini()
    
    # Create application
    application = Application.builder().token(TG_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("categories", show_categories))
    application.add_handler(CommandHandler("add", add_domain_manual))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_domain))
    
    # Run bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
