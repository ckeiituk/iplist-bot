import logging
import asyncio
import httpx
from telegram import Update
from telegram.ext import ContextTypes
from config import LOG_CHANNEL_ID
from services.gemini import classify_domain, resolve_domain_from_keyword
from services.dns import resolve_dns
from services.github import get_categories_from_github, create_site_json, create_file_in_github
from state import pending_builds

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне домен (например, `netflix.com` или просто `netflix`), "
        "и я добавлю его в репозиторий iplist."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/start - Начать работу\n"
        "/add <домен> <категория> - Ручное добавление домена в категорию\n"
        "Либо просто отправь домен сообщением, и я попробую определить категорию сам."
    )

async def add_domain_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /add <домен> <категория>")
        return
    
    domain = args[0].lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
    category = args[1].lower()
    
    status_msg = await update.message.reply_text(f"⏳ Обрабатываю {domain}...")
    
    try:
        # Step 1: Validate category by fetching list
        categories = await get_categories_from_github()
        
        # Check if category exists (case-insensitive)
        real_category = None
        for c in categories:
            if c.lower() == category:
                real_category = c
                break
        
        if not real_category:
            await status_msg.edit_text(f"❌ Категория '{category}' не найдена. Доступные: {', '.join(categories)}")
            return
            
        # Step 2: Resolve DNS
        await status_msg.edit_text(f"🔍 Резолвлю DNS для {domain}...")
        ip4, ip6 = resolve_dns(domain)
        
        if not ip4 and not ip6:
            await status_msg.edit_text(f"❌ Не удалось получить IP для {domain}.")
            return

        # Step 3: Create GitHub file
        site_json = create_site_json(domain, ip4, ip6)
        
        await status_msg.edit_text(f"📤 Создаю файл в репозитории...")
        html_url, commit_sha = await create_file_in_github(real_category, domain, site_json)
        
        # Track pending build
        pending_builds[commit_sha] = {
            'user_id': update.effective_user.id,
            'domain': domain,
            'chat_id': update.effective_chat.id,
            'bot': context.bot
        }

        # Success info
        ip_info = []
        if ip4: ip_info.append(f"IPv4: {', '.join(ip4)}")
        if ip6: ip_info.append(f"IPv6: {', '.join(ip6)}")
        
        await status_msg.edit_text(
            f"✅ Готово! Файл создан.\n"
            f"Ожидаю сборку... ⏳\n\n"
            f"📁 Категория: {real_category}\n"
            f"🌐 {chr(10).join(ip_info)}"
        )
        
        await send_log_report(context.bot, update.effective_user, domain, real_category, ip4, ip6, html_url)

    except Exception as e:
        logger.error(f"Manual add error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text: return
    
    domain = text.lower()
    # Basic cleanup
    domain = domain.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
    
    status_msg = await update.message.reply_text(f"⏳ Обрабатываю {domain}...")
    
    try:
        # Step 0: Smart resolve keyword -> domain
        if "." not in domain:
            await status_msg.edit_text(f"🔍 Определяю домен для '{domain}'...")
            try:
                resolved_domain = await resolve_domain_from_keyword(domain)
                await status_msg.edit_text(
                    f"✅ Найден домен: `{resolved_domain}`\n"
                    f"Продолжаю..."
                )
                domain = resolved_domain
                await asyncio.sleep(1)
            except ValueError as e:
                await status_msg.edit_text(f"❓ {str(e)}\nУточни домен.")
                return

        # Step 1: Categories
        await status_msg.edit_text(f"📂 Получаю категории...")
        categories = await get_categories_from_github()
        
        # Step 2: Classify
        await status_msg.edit_text(f"🤖 Определяю категорию для {domain}...")
        category = await classify_domain(domain, categories)
        
        # Step 3: DNS
        await status_msg.edit_text(f"🔍 Резолвлю DNS...")
        ip4, ip6 = resolve_dns(domain)
        
        if not ip4 and not ip6:
            await status_msg.edit_text(f"❌ Не удалось получить IP для {domain}.")
            return
            
        # Step 4: GitHub
        site_json = create_site_json(domain, ip4, ip6)
        
        await status_msg.edit_text(f"📤 Создаю файл...")
        html_url, commit_sha = await create_file_in_github(category, domain, site_json)
        
        # Track pending
        pending_builds[commit_sha] = {
            'user_id': update.effective_user.id,
            'domain': domain,
            'chat_id': update.effective_chat.id,
            'bot': context.bot
        }
        
        # Result
        ip_info = []
        if ip4: ip_info.append(f"IPv4: {', '.join(ip4)}")
        if ip6: ip_info.append(f"IPv6: {', '.join(ip6)}")
        
        await status_msg.edit_text(
            f"✅ Готово!\n"
            f"Ожидаю сборку... ⏳\n\n"
            f"📁 Категория: {category}\n"
            f"🌐 {chr(10).join(ip_info)}"
        )
        
        await send_log_report(context.bot, update.effective_user, domain, category, ip4, ip6, html_url)
        
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")

async def send_log_report(bot, user, domain, category, ip4, ip6, html_url):
    if not LOG_CHANNEL_ID: return
    
    try:
        user_mention = f"@{user.username}" if user.username else user.full_name
        
        msg = (
            f"🆕 **Новый домен добавлен**\n"
            f"👤 От: {user_mention} (`{user.id}`)\n"
            f"🌐 Домен: `{domain}`\n"
            f"📁 Категория: `{category}`\n"
            f"📄 [JSON файл]({html_url})"
        )
        await bot.send_message(chat_id=LOG_CHANNEL_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Log report error: {e}")
