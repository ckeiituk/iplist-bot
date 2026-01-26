"""Admin reminder command handler."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, time, timedelta, timezone, tzinfo
from typing import Coroutine
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.core.config import settings
from bot.core.logging import get_logger

logger = get_logger(__name__)

REMIND_TARGET, REMIND_WHEN, REMIND_MESSAGE = range(3)

_USAGE_TEXT = (
    "Использование:\n"
    "/remind <user_id|@username> <YYYY-MM-DD HH:MM> <сообщение>\n"
    "Можно указать ссылку t.me/username.\n"
    "Пример: /remind 123456789 2024-06-30 09:00 Напомнить про оплату\n"
    "Время — по Москве (MSK)."
)

_PROMPT_TARGET = (
    "Кому напомнить? Укажи user_id или @username (пользователь должен писать боту). "
    "Можно ответом на сообщение. /cancel — выйти."
)
_PROMPT_WHEN = "Когда? Формат: YYYY-MM-DD HH:MM или HH:MM (сегодня/завтра, MSK)."
_PROMPT_MESSAGE = "Что написать пользователю?"

_USER_NOT_FOUND_TEXT = (
    "Не удалось найти пользователя. @username работает только если пользователь писал боту "
    "или есть общий чат. Попробуй ответить на сообщение пользователя или указать user_id."
)

_DOMAIN_IN_REMIND_TEXT = (
    "Похоже, это домен или ссылка. /remind принимает user_id или @username. "
    "Если нужно добавить домен — используй /add <домен> <категория> или /cancel и отправь "
    "домен отдельным сообщением."
)

_TIME_ONLY_RE = re.compile(r"^\d{1,2}:\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TME_USERNAME_RE = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me)/(?P<username>[A-Za-z0-9_]{5,})(?:/)?(?:\?.*)?$",
    re.IGNORECASE,
)
_DOMAIN_TOKEN_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/.*)?$",
    re.IGNORECASE,
)

_REMINDER_TARGET_ID_KEY = "reminder_target_id"
_REMINDER_TARGET_LABEL_KEY = "reminder_target_label"
_REMINDER_WHEN_KEY = "reminder_when"


def _get_reminder_timezone() -> tzinfo:
    tz_name = settings.reminder_timezone or "Europe/Moscow"
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Timezone %s not found, falling back to MSK offset.", tz_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load timezone %s: %s", tz_name, exc)
    return timezone(timedelta(hours=3), name="MSK")


def _as_timezone(value: datetime, tz: tzinfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def _parse_datetime_tokens(tokens: list[str], now: datetime) -> tuple[datetime, int]:
    if not tokens:
        raise ValueError("empty")

    first = tokens[0]
    if _TIME_ONLY_RE.match(first):
        scheduled = _apply_time_only(first, now)
        return scheduled, 1

    if "T" in first:
        return _as_timezone(datetime.fromisoformat(first), now.tzinfo or _get_reminder_timezone()), 1

    if _DATE_RE.match(first) and len(tokens) >= 2:
        candidate = f"{tokens[0]} {tokens[1]}"
        return _as_timezone(datetime.fromisoformat(candidate), now.tzinfo or _get_reminder_timezone()), 2

    if len(tokens) < 2:
        raise ValueError("missing time")

    if ":" not in tokens[1]:
        raise ValueError("missing time")

    candidate = f"{tokens[0]} {tokens[1]}"
    return _as_timezone(datetime.fromisoformat(candidate), now.tzinfo or _get_reminder_timezone()), 2


def _normalize_user_token(user_token: str) -> str:
    normalized = user_token.strip()
    match = _TME_USERNAME_RE.match(normalized)
    if match:
        return f"@{match.group('username')}"
    return normalized


def _looks_like_domain_token(token: str) -> bool:
    if token.startswith("@"):
        return False
    if token.isdigit():
        return False
    return bool(_DOMAIN_TOKEN_RE.match(token))


def _format_datetime(value: datetime) -> str:
    tz = _get_reminder_timezone()
    localized = _as_timezone(value, tz)
    tz_name = localized.tzname() or "MSK"
    return f"{localized.strftime('%Y-%m-%d %H:%M')} {tz_name}"


def _apply_time_only(value: str, now: datetime) -> datetime:
    parsed = time.fromisoformat(value)
    scheduled = datetime.combine(now.date(), parsed, tzinfo=now.tzinfo)
    if scheduled <= now:
        scheduled += timedelta(days=1)
    return scheduled


def _parse_when_text(text: str) -> datetime:
    cleaned = text.strip()
    tz = _get_reminder_timezone()
    now = datetime.now(tz)

    if _TIME_ONLY_RE.match(cleaned):
        return _apply_time_only(cleaned, now)

    if "T" in cleaned:
        return _as_timezone(datetime.fromisoformat(cleaned), tz)

    if _DATE_RE.match(cleaned):
        raise ValueError("date without time")

    return _as_timezone(datetime.fromisoformat(cleaned), tz)


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
    scheduled_for: datetime,
    requested_by: str | None,
    target_label: str | None,
) -> None:
    try:
        await asyncio.sleep(delay_seconds)
        await context.bot.send_message(chat_id=chat_id, text=message)
    except asyncio.CancelledError:
        logger.info("Reminder task cancelled for chat %s.", chat_id)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send reminder to %s: %s", chat_id, exc)
        await _send_reminder_failure_log(
            context,
            chat_id=chat_id,
            target_label=target_label,
            scheduled_for=scheduled_for,
            requested_by=requested_by,
            message=message,
            error=exc,
        )


async def _send_reminder_failure_log(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    target_label: str | None,
    scheduled_for: datetime,
    requested_by: str | None,
    message: str,
    error: Exception,
) -> None:
    if not settings.channel_id:
        return

    recipient = target_label or str(chat_id)
    requester = requested_by or "—"
    text = (
        "⚠️ Напоминание не доставлено\n"
        f"Получатель: {recipient}\n"
        f"Когда: {_format_datetime(scheduled_for)}\n"
        f"Кто поставил: {requester}\n"
        f"Ошибка: {error}\n"
        f"Текст: {message}"
    )

    kwargs = {
        "chat_id": settings.channel_id,
        "text": text,
    }
    if settings.topic_id:
        kwargs["message_thread_id"] = settings.topic_id

    try:
        await context.bot.send_message(**kwargs)
    except Exception as log_exc:  # noqa: BLE001
        logger.warning("Failed to send reminder failure log: %s", log_exc)


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


def _format_user_identity(update: Update) -> str | None:
    user = update.effective_user
    if not user:
        return None
    username = f"@{user.username}" if user.username else user.full_name
    return f"{username} ({user.id})"


def _clear_reminder_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(_REMINDER_TARGET_ID_KEY, None)
    context.user_data.pop(_REMINDER_TARGET_LABEL_KEY, None)
    context.user_data.pop(_REMINDER_WHEN_KEY, None)


def _get_replied_user_id(update: Update) -> int | None:
    if not update.effective_message:
        return None
    reply_to = update.effective_message.reply_to_message
    if not reply_to or not reply_to.from_user:
        return None
    if reply_to.from_user.is_bot:
        return None
    return reply_to.from_user.id


def _get_replied_user_label(update: Update) -> str | None:
    if not update.effective_message:
        return None
    reply_to = update.effective_message.reply_to_message
    if not reply_to or not reply_to.from_user:
        return None
    user = reply_to.from_user
    if user.is_bot:
        return None
    username = f"@{user.username}" if user.username else user.full_name
    return f"{username} ({user.id})"


async def _ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    reply = _get_reply_target(update)
    if reply is None:
        return False

    admin_ids = settings.admin_ids
    if not admin_ids:
        await reply("Администраторы не настроены. Укажи ADMIN_USER_IDS.")
        return False

    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in admin_ids:
        await reply("Команда доступна только администраторам.")
        return False
    return True


async def handle_admin_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /remind admin command."""
    if not await _ensure_admin(update, context):
        return ConversationHandler.END

    args = context.args or []
    if args:
        return await _handle_direct_reminder(update, context, args)

    replied_user_id = _get_replied_user_id(update)
    if replied_user_id:
        context.user_data[_REMINDER_TARGET_ID_KEY] = replied_user_id
        label = _get_replied_user_label(update)
        if label:
            context.user_data[_REMINDER_TARGET_LABEL_KEY] = label
        reply = _get_reply_target(update)
        if reply:
            await reply(_PROMPT_WHEN)
        return REMIND_WHEN

    reply = _get_reply_target(update)
    if reply:
        await reply(_PROMPT_TARGET)
    return REMIND_TARGET


async def _handle_direct_reminder(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    args: list[str],
) -> int:
    reply = _get_reply_target(update)
    if reply is None:
        return ConversationHandler.END

    if len(args) < 2:
        await reply(_USAGE_TEXT)
        return ConversationHandler.END

    user_token = _normalize_user_token(args[0])
    if _looks_like_domain_token(user_token):
        await reply(_DOMAIN_IN_REMIND_TEXT)
        return ConversationHandler.END
    parse_now = datetime.now(_get_reminder_timezone())

    try:
        scheduled_for, consumed = _parse_datetime_tokens(args[1:], parse_now)
    except ValueError:
        await reply(_USAGE_TEXT)
        return ConversationHandler.END

    message_tokens = args[1 + consumed:]
    if not message_tokens:
        await reply(_USAGE_TEXT)
        return ConversationHandler.END

    now = datetime.now(tz=scheduled_for.tzinfo) if scheduled_for.tzinfo else datetime.now()
    delay_seconds = (scheduled_for - now).total_seconds()
    if delay_seconds <= 0:
        await reply("Время напоминания должно быть в будущем.")
        return ConversationHandler.END

    try:
        target_chat_id, target_label = await _resolve_target_chat_id(user_token, context)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to resolve user %s: %s", user_token, exc)
        await reply(_USER_NOT_FOUND_TEXT)
        return ConversationHandler.END

    message = " ".join(message_tokens)
    _schedule_reminder_task(
        _send_reminder_after_delay(
            context,
            chat_id=target_chat_id,
            message=message,
            delay_seconds=delay_seconds,
            scheduled_for=scheduled_for,
            requested_by=_format_user_identity(update),
            target_label=target_label,
        )
    )

    await reply(
        "✅ Напоминание поставлено.\n"
        f"Получатель: {target_label}\n"
        f"Когда: {_format_datetime(scheduled_for)}\n"
        f"Текст: {message}"
    )
    return ConversationHandler.END


async def handle_reminder_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reply = _get_reply_target(update)
    if reply is None:
        return ConversationHandler.END

    text = update.effective_message.text.strip() if update.effective_message else ""
    if not text:
        await reply(_PROMPT_TARGET)
        return REMIND_TARGET

    text = _normalize_user_token(text)
    if _looks_like_domain_token(text):
        await reply(_DOMAIN_IN_REMIND_TEXT)
        return REMIND_TARGET

    try:
        target_chat_id, target_label = await _resolve_target_chat_id(text, context)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to resolve user %s: %s", text, exc)
        await reply(_USER_NOT_FOUND_TEXT)
        return REMIND_TARGET

    context.user_data[_REMINDER_TARGET_ID_KEY] = target_chat_id
    context.user_data[_REMINDER_TARGET_LABEL_KEY] = target_label

    await reply(_PROMPT_WHEN)
    return REMIND_WHEN


async def handle_reminder_when(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reply = _get_reply_target(update)
    if reply is None:
        return ConversationHandler.END

    text = update.effective_message.text.strip() if update.effective_message else ""
    if not text:
        await reply(_PROMPT_WHEN)
        return REMIND_WHEN

    try:
        scheduled_for = _parse_when_text(text)
    except ValueError:
        await reply(_PROMPT_WHEN)
        return REMIND_WHEN

    now = datetime.now(tz=scheduled_for.tzinfo) if scheduled_for.tzinfo else datetime.now()
    if scheduled_for <= now:
        await reply("Время напоминания должно быть в будущем.")
        return REMIND_WHEN

    context.user_data[_REMINDER_WHEN_KEY] = scheduled_for
    await reply(_PROMPT_MESSAGE)
    return REMIND_MESSAGE


async def handle_reminder_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reply = _get_reply_target(update)
    if reply is None:
        return ConversationHandler.END

    text = update.effective_message.text.strip() if update.effective_message else ""
    if not text:
        await reply(_PROMPT_MESSAGE)
        return REMIND_MESSAGE

    target_chat_id = context.user_data.get(_REMINDER_TARGET_ID_KEY)
    scheduled_for = context.user_data.get(_REMINDER_WHEN_KEY)
    target_label = context.user_data.get(_REMINDER_TARGET_LABEL_KEY, str(target_chat_id))

    if not target_chat_id or not scheduled_for:
        _clear_reminder_state(context)
        await reply(_USAGE_TEXT)
        return ConversationHandler.END

    now = datetime.now(tz=scheduled_for.tzinfo) if scheduled_for.tzinfo else datetime.now()
    delay_seconds = (scheduled_for - now).total_seconds()
    if delay_seconds <= 0:
        _clear_reminder_state(context)
        await reply("Время напоминания должно быть в будущем.")
        return ConversationHandler.END

    _schedule_reminder_task(
        _send_reminder_after_delay(
            context,
            chat_id=target_chat_id,
            message=text,
            delay_seconds=delay_seconds,
            scheduled_for=scheduled_for,
            requested_by=_format_user_identity(update),
            target_label=target_label,
        )
    )

    _clear_reminder_state(context)
    await reply(
        "✅ Напоминание поставлено.\n"
        f"Получатель: {target_label}\n"
        f"Когда: {_format_datetime(scheduled_for)}\n"
        f"Текст: {text}"
    )
    return ConversationHandler.END


async def cancel_admin_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reply = _get_reply_target(update)
    if reply is not None:
        await reply("Ок, отменил.")
    _clear_reminder_state(context)
    return ConversationHandler.END


def build_admin_reminder_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("remind", handle_admin_reminder),
            CommandHandler("reminder", handle_admin_reminder),
        ],
        states={
            REMIND_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reminder_target)],
            REMIND_WHEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reminder_when)],
            REMIND_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reminder_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_reminder)],
        allow_reentry=True,
    )
