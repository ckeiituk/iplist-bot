"""
Common utilities for handlers.
"""

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, User
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


async def send_payment_request(
    bot: Bot,
    user: User,
    payment: dict,
) -> None:
    """Send a payment request to the admin channel/topic."""
    if not settings.lk_admin_channel:
        return

    user_mention = f"@{user.username}" if user.username else user.full_name
    payment_id = payment.get("id", "—")
    amount = float(payment.get("amount") or 0)
    status = payment.get("status", "—")
    due_date = payment.get("due_date") or "—"
    comment = payment.get("comment") or "—"

    msg = (
        "🧾 Запрос подтверждения оплаты\n"
        f"👤 Пользователь: {user_mention} ({user.id})\n"
        f"🔖 Платеж: #{payment_id}\n"
        f"💰 Сумма: {amount:.2f} ₽\n"
        f"📌 Статус: {status}\n"
        f"📅 Дата: {due_date}\n"
        f"📝 Комментарий: {comment}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "Подтвердить",
                callback_data=f"admin_payment:confirm:{payment_id}:{user.id}",
            ),
            InlineKeyboardButton(
                "Отклонить",
                callback_data=f"admin_payment:decline:{payment_id}:{user.id}",
            ),
        ]
    ])

    kwargs = {
        "chat_id": settings.lk_admin_channel,
        "text": msg,
        "reply_markup": keyboard,
    }
    if settings.lk_admin_topic:
        kwargs["message_thread_id"] = settings.lk_admin_topic

    try:
        await bot.send_message(**kwargs)
    except Exception as e:
        logger.error(f"Payment request error: {e}")
