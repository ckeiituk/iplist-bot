"""Admin reminder command handler."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Coroutine

from telegram import Update
from telegram.ext import ContextTypes

from bot.core.config import settings
from bot.core.logging import get_logger

logger = get_logger(__name__)

_USAGE_TEXT = (
    "Использование:\n"
    "/remind <user_id|@username> <YYYY-MM-DD HH:MM> <сообщение>\n"
    "Пример: /remind 123456789 2024-06-30 09:00 Напомнить про оплату\n"
    "Время — по часовому поясу сервера."
)


def _parse_datetime_tokens(tokens: list[str]) -> tuple[datetime, int]:
    if not tokens:
        raise ValueError("empty")

    first = tokens[0]
    if ":" in first or "T" in first:
        try:
            return datetime.fromisoformat(first), 1
        except ValueError:
            pass

    if len(tokens) < 2:
        raise ValueError("missing time")

    if ":" not in tokens[1]:
        raise ValueError("missing time")

    candidate = f"{tokens[0]} {tokens[1]}"
    return datetime.fromisoformat(candidate), 2


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.isoformat(timespec="minutes")


async def _resolve_target_chat_id(
    user_token: str,
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[int, str]:
    normalized = user_token.strip()
    numeric = normalized.lstrip("@")
    if numeric.isdigit():
        chat_id = int(numeric)
        return chat_id, f"{chat_id}"

    username = normalized if normalized.startswith("@") else f"@{normalized}"
    chat = await context.bot.get_chat(username)
    label = f"{username} ({chat.id})"
    return chat.id, label


async def _send_reminder_after_delay(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    message: str,
    delay_seconds: float,
) -> None:
    try:
        await asyncio.sleep(delay_seconds)
        await context.bot.send_message(chat_id=chat_id, text=message)
    except asyncio.CancelledError:
        logger.info("Reminder task cancelled for chat %s.", chat_id)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send reminder to %s: %s", chat_id, exc)


def _schedule_reminder_task(coro: Coroutine[None, None, None]) -> None:
    task = asyncio.create_task(coro)

    def _handle_task_result(done_task: asyncio.Task) -> None:
        try:
            done_task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            logger.error("Reminder task failed: %s", exc)

    task.add_done_callback(_handle_task_result)


def _get_reply_target(update: Update):
    if update.effective_message:
        return update.effective_message.reply_text
    if update.message:
        return update.message.reply_text
    return None


async def handle_admin_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remind admin command."""
    reply = _get_reply_target(update)
    if reply is None:
        return

    admin_ids = settings.admin_ids
    if not admin_ids:
        await reply("Администраторы не настроены. Укажи ADMIN_USER_IDS.")
        return

    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in admin_ids:
        await reply("Команда доступна только администраторам.")
        return

    args = context.args or []
    if len(args) < 3:
        await reply(_USAGE_TEXT)
        return

    user_token = args[0]
    try:
        scheduled_for, consumed = _parse_datetime_tokens(args[1:])
    except ValueError:
        await reply(_USAGE_TEXT)
        return

    message_tokens = args[1 + consumed:]
    if not message_tokens:
        await reply(_USAGE_TEXT)
        return

    now = datetime.now(tz=scheduled_for.tzinfo) if scheduled_for.tzinfo else datetime.now()
    delay_seconds = (scheduled_for - now).total_seconds()
    if delay_seconds <= 0:
        await reply("Время напоминания должно быть в будущем.")
        return

    try:
        target_chat_id, target_label = await _resolve_target_chat_id(user_token, context)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to resolve user %s: %s", user_token, exc)
        await reply("Не удалось найти пользователя. Укажи user_id или @username.")
        return

    message = " ".join(message_tokens)
    _schedule_reminder_task(
        _send_reminder_after_delay(
            context,
            chat_id=target_chat_id,
            message=message,
            delay_seconds=delay_seconds,
        )
    )

    await reply(
        "✅ Напоминание поставлено.\n"
        f"Получатель: {target_label}\n"
        f"Когда: {_format_datetime(scheduled_for)}\n"
        f"Текст: {message}"
    )
