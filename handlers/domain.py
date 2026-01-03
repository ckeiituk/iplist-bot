"""
Domain addition handlers.
"""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from bot.core.config import settings
from bot.core.logging import get_logger
from bot.models.pending import PendingBuild
from bot.state.builds import pending_builds
from bot.services.dns import resolve_dns
from bot.services.search import WebSearcher
from bot.services.ai.client import GeminiClient
from bot.services.ai.classifier import classify_domain
from bot.services.ai.resolver import resolve_domain_from_keyword
from bot.services.github.client import GitHubClient
from bot.services.github.schemas import SiteConfig
from bot.handlers.common import send_log_report

logger = get_logger(__name__)

# Initialize clients
_gemini_client = GeminiClient(settings.gemini_api_keys, settings.gemini_model)
_github_client = GitHubClient(settings.github_token, settings.github_repo, settings.github_branch)
_web_searcher = WebSearcher()


def _clean_domain(text: str) -> str:
    """Clean and normalize domain input."""
    return (
        text.lower()
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .rstrip("/")
    )


def _get_message_thread_id(update: Update) -> int | None:
    """Get message thread ID if in a topic."""
    msg = update.effective_message
    if msg and msg.is_topic_message:
        return msg.message_thread_id
    return None


async def add_domain_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /add <domain> <category> command."""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /add <домен> <категория>")
        return
    
    domain = _clean_domain(args[0])
    category_input = args[1].lower()
    
    status_msg = await update.message.reply_text(f"⏳ Обрабатываю {domain}...")
    
    try:
        # Step 1: Validate category
        categories = await _github_client.get_categories()
        
        real_category = None
        for c in categories:
            if c.lower() == category_input:
                real_category = c
                break
        
        if not real_category:
            await status_msg.edit_text(
                f"❌ Категория '{category_input}' не найдена. "
                f"Доступные: {', '.join(categories)}"
            )
            return
        
        # Step 2: Resolve DNS
        await status_msg.edit_text(f"🔍 Резолвлю DNS для {domain}...")
        ip4, ip6 = resolve_dns(domain)
        
        if not ip4 and not ip6:
            await status_msg.edit_text(f"❌ Не удалось получить IP для {domain}.")
            return
        
        # Step 3: Create GitHub file
        site_config = SiteConfig.create(domain, settings.dns_servers, ip4, ip6)
        
        await status_msg.edit_text("📤 Создаю файл в репозитории...")
        html_url, commit_sha = await _github_client.create_file(
            real_category, domain, site_config
        )
        
        # Track pending build
        pending_builds.add(
            commit_sha,
            PendingBuild(
                user_id=update.effective_user.id,
                domain=domain,
                chat_id=update.effective_chat.id,
                bot=context.bot,
                message_thread_id=_get_message_thread_id(update),
            ),
        )
        
        # Success message
        ip_info = []
        if ip4:
            ip_info.append(f"IPv4: {', '.join(ip4)}")
        if ip6:
            ip_info.append(f"IPv6: {', '.join(ip6)}")
        
        await status_msg.edit_text(
            f"✅ Готово! Файл создан.\n"
            f"Ожидаю сборку... ⏳\n\n"
            f"📁 Категория: {real_category}\n"
            f"🌐 {chr(10).join(ip_info)}"
        )
        
        await send_log_report(
            context.bot, update.effective_user, domain, real_category, ip4, ip6, html_url
        )
        
    except Exception as e:
        logger.error(f"Manual add error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages (domain input)."""
    text = update.message.text.strip()
    if not text:
        return
    
    domain = _clean_domain(text)
    status_msg = await update.message.reply_text(f"⏳ Обрабатываю {domain}...")
    
    try:
        # Step 0: Resolve keyword -> domain if no dot
        if "." not in domain:
            await status_msg.edit_text(f"🔍 Определяю домен для '{domain}'...")
            try:
                resolved_domain = await resolve_domain_from_keyword(_gemini_client, domain)
                await status_msg.edit_text(
                    f"✅ Найден домен: `{resolved_domain}`\nПродолжаю..."
                )
                domain = resolved_domain
                await asyncio.sleep(1)
            except ValueError as e:
                await status_msg.edit_text(f"❓ {str(e)}\nУточни домен.")
                return
        
        # Step 1: Get categories
        await status_msg.edit_text("📂 Получаю категории...")
        categories = await _github_client.get_categories()
        
        # Step 2: Classify domain
        await status_msg.edit_text(f"🤖 Определяю категорию для {domain}...")
        category = await classify_domain(_gemini_client, _web_searcher, domain, categories)
        
        # Step 3: DNS resolution
        await status_msg.edit_text("🔍 Резолвлю DNS...")
        ip4, ip6 = resolve_dns(domain)
        
        if not ip4 and not ip6:
            await status_msg.edit_text(f"❌ Не удалось получить IP для {domain}.")
            return
        
        # Step 4: Create GitHub file
        site_config = SiteConfig.create(domain, settings.dns_servers, ip4, ip6)
        
        await status_msg.edit_text("📤 Создаю файл...")
        html_url, commit_sha = await _github_client.create_file(category, domain, site_config)
        
        # Track pending build
        pending_builds.add(
            commit_sha,
            PendingBuild(
                user_id=update.effective_user.id,
                domain=domain,
                chat_id=update.effective_chat.id,
                bot=context.bot,
                message_thread_id=_get_message_thread_id(update),
            ),
        )
        
        # Result message
        ip_info = []
        if ip4:
            ip_info.append(f"IPv4: {', '.join(ip4)}")
        if ip6:
            ip_info.append(f"IPv6: {', '.join(ip6)}")
        
        await status_msg.edit_text(
            f"✅ Готово!\n"
            f"Ожидаю сборку... ⏳\n\n"
            f"📁 Категория: {category}\n"
            f"🌐 {chr(10).join(ip_info)}"
        )
        
        await send_log_report(
            context.bot, update.effective_user, domain, category, ip4, ip6, html_url
        )
        
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")
