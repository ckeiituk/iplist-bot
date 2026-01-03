"""
Common utilities for handlers.
"""

from telegram import Bot, User
from bot.core.config import settings
from bot.core.logging import get_logger

logger = get_logger(__name__)


async def send_log_report(
    bot: Bot,
    user: User,
    domain: str,
    category: str,
    ip4: list[str],
    ip6: list[str],
    html_url: str,
) -> None:
    """
    Send a log report to the configured log channel.
    
    Args:
        bot: Telegram bot instance
        user: User who added the domain
        domain: Added domain
        category: Assigned category
        ip4: IPv4 addresses
        ip6: IPv6 addresses
        html_url: GitHub file URL
    """
    if not settings.channel_id:
        return
    
    try:
        user_mention = f"@{user.username}" if user.username else user.full_name
        
        msg = (
            f"🆕 **Новый домен добавлен**\n"
            f"👤 От: {user_mention} (`{user.id}`)\n"
            f"🌐 Домен: `{domain}`\n"
            f"📁 Категория: `{category}`\n"
            f"📄 [JSON файл]({html_url})"
        )
        
        kwargs = {
            "chat_id": settings.channel_id,
            "text": msg,
            "parse_mode": "Markdown",
        }
        if settings.topic_id:
            kwargs["message_thread_id"] = settings.topic_id
        
        await bot.send_message(**kwargs)
    except Exception as e:
        logger.error(f"Log report error: {e}")
