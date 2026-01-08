"""
Domain addition handlers.
"""

import asyncio
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.core.config import settings
from bot.core.logging import get_logger
from bot.handlers.common import send_log_report
from bot.handlers.menu import show_main_menu
from bot.models.pending import PendingBuild
from bot.services.ai.classifier import classify_domain
from bot.services.ai.client import GeminiClient
from bot.services.ai.resolver import resolve_domain_from_keyword
from bot.services.dns import resolve_dns_with_reason
from bot.services.github.client import GitHubClient
from bot.services.github.schemas import SiteConfig
from bot.services.search import WebSearcher
from bot.state.builds import pending_builds

logger = get_logger(__name__)

# Initialize clients
_gemini_client = GeminiClient(settings.gemini_api_keys, settings.gemini_model)
_github_client = GitHubClient(settings.github_token, settings.github_repo, settings.github_branch)
_web_searcher = WebSearcher()

_DOMAIN_RE = re.compile(r"(https?://)?(www\.)?([a-z0-9-]+(\.[a-z0-9-]+)+)", re.IGNORECASE)


def _clean_domain(text: str) -> str:
    """Clean and normalize domain input."""
    return (
        text.lower()
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .rstrip("/")
    )


def _extract_domain(text: str) -> str | None:
    match = _DOMAIN_RE.search(text)
    if not match:
        return None
    return _clean_domain(match.group(3))


def _infer_lk_section(text: str) -> str | None:
    lowered = text.lower()
    if any(token in lowered for token in ("лк", "кабинет", "личн", "lk", "account")):
        return "summary"
    if any(token in lowered for token in ("подпис", "subscription")):
        return "subscriptions"
    if any(token in lowered for token in ("платеж", "оплат", "payment")):
        return "payments"
    if any(token in lowered for token in ("займ", "loan")):
        return "loans"
    if "истор" in lowered or "операц" in lowered:
        return "history"
    if "баланс" in lowered:
        return "balance"
    return None


def _infer_menu_view(text: str) -> str | None:
    lowered = text.lower()
    if any(token in lowered for token in ("help", "помощ", "что умеешь", "инструкция")):
        return "help"
    if any(token in lowered for token in ("меню", "menu", "главное меню")):
        return "main"
    return None


def _format_dns_notice(domain: str, issue: str | None) -> str:
    if issue == "nxdomain":
        return f"⚠️ DNS: домен не найден (NXDOMAIN): {domain}. Продолжаю без IP."
    if issue == "no_answer":
        return f"⚠️ DNS: нет A/AAAA записей для {domain}. Продолжаю без IP."
    if issue == "no_nameservers":
        return f"⚠️ DNS: серверы не отвечают для {domain}. Продолжаю без IP."
    if issue == "timeout":
        return f"⚠️ DNS: таймаут запроса для {domain}. Продолжаю без IP."
    return f"⚠️ DNS: не удалось получить IP для {domain}. Продолжаю без IP."


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
        dns_result = resolve_dns_with_reason(domain)
        ip4, ip6 = dns_result.ip4, dns_result.ip6
        dns_notice = ""
        if not ip4 and not ip6:
            dns_notice = _format_dns_notice(domain, dns_result.issue)

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
        ip_lines = chr(10).join(ip_info) if ip_info else "IP не найден"

        message_text = (
            "✅ Готово! Файл создан.\n"
            "Ожидаю сборку... ⏳\n\n"
        )
        if dns_notice:
            message_text += f"{dns_notice}\n"
        message_text += f"📁 Категория: {real_category}\n🌐 {ip_lines}"

        await status_msg.edit_text(message_text)

        await send_log_report(
            context.bot, update.effective_user, domain, real_category, ip4, ip6, html_url
        )

    except Exception as e:
        logger.error(f"Manual add error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route text messages to LK or domain flow."""
    text = update.message.text.strip()
    if not text:
        return

    domain = _extract_domain(text)
    if domain:
        await _ask_domain_action(update, context, domain)
        return

    menu_view = _infer_menu_view(text)
    if menu_view:
        await show_main_menu(update, context, view=menu_view)
        return

    section = _infer_lk_section(text)
    if section:
        from bot.handlers.lk import lk_start

        await lk_start(update, context, section=section)
        return

    await show_main_menu(update, context)


async def handle_domain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle domain clarification buttons."""
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    await query.answer()

    if data == "domain:cancel":
        await query.edit_message_text("Ок, отменил.")
        context.user_data.pop("pending_domain", None)
        return

    if data == "domain:lk":
        from bot.handlers.lk import lk_start

        context.user_data.pop("pending_domain", None)
        await lk_start(update, context, section="summary")
        return

    if data == "domain:add":
        domain = context.user_data.pop("pending_domain", None)
        if not domain:
            await query.edit_message_text("Не нашел домен. Отправь его еще раз.")
            return
        await _process_domain(update, context, domain, query.message)


async def _ask_domain_action(update: Update, context: ContextTypes.DEFAULT_TYPE, domain: str) -> None:
    context.user_data["pending_domain"] = domain
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Добавить домен", callback_data="domain:add"),
            InlineKeyboardButton("Открыть ЛК", callback_data="domain:lk"),
        ],
        [InlineKeyboardButton("Отмена", callback_data="domain:cancel")],
    ])
    await update.message.reply_text(
        f"Вижу домен: {domain}. Что сделать?",
        reply_markup=keyboard,
    )


async def _process_domain(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    domain: str,
    message,
) -> None:
    status_msg = await message.reply_text(f"⏳ Обрабатываю {domain}...")

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
        dns_result = resolve_dns_with_reason(domain)
        ip4, ip6 = dns_result.ip4, dns_result.ip6
        dns_notice = ""
        if not ip4 and not ip6:
            dns_notice = _format_dns_notice(domain, dns_result.issue)

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
        ip_lines = chr(10).join(ip_info) if ip_info else "IP не найден"

        message_text = "✅ Готово!\nОжидаю сборку... ⏳\n\n"
        if dns_notice:
            message_text += f"{dns_notice}\n"
        message_text += f"📁 Категория: {category}\n🌐 {ip_lines}"

        await status_msg.edit_text(message_text)

        await send_log_report(
            context.bot, update.effective_user, domain, category, ip4, ip6, html_url
        )

    except Exception as e:
        logger.error(f"Handler error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")
