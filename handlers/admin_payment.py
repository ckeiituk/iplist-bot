"""Admin payment approval handlers."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.core.config import settings
from bot.core.exceptions import CollectorAPIError
from bot.core.logging import get_logger
from bot.services.collector import CollectorApiClient

logger = get_logger(__name__)

_api_client: CollectorApiClient | None = None


def _get_api_client() -> CollectorApiClient:
    global _api_client
    if _api_client is None:
        _api_client = CollectorApiClient(settings.site_api_base_url, settings.site_api_key)
    return _api_client


def _build_admin_status_line(action: str, result: str) -> str:
    if result == "already_paid":
        return "ℹ️ Уже подтверждено ранее."
    if result == "cancelled":
        return "ℹ️ Платеж отменен."
    if action == "confirm":
        return "✅ Подтверждено админом."
    return "❌ Отклонено админом."


def _build_user_notification(action: str, payment_id: int, result: str) -> str:
    if result == "already_paid":
        return f"Платеж #{payment_id} уже подтвержден."
    if result == "cancelled":
        return f"Платеж #{payment_id} отменен."
    if action == "confirm":
        return f"Оплата по платежу #{payment_id} подтверждена. Спасибо!"
    return (
        f"Оплата по платежу #{payment_id} отклонена. "
        "Если уже оплатил — напиши админу или приложи чек."
    )


async def _update_admin_message(update: Update, status_line: str) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
    base_text = query.message.text or ""
    if status_line in base_text:
        return
    text = f"{base_text}\n\n{status_line}" if base_text else status_line
    await query.edit_message_text(text=text)


async def _notify_user(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    message: str,
) -> None:
    try:
        await context.bot.send_message(chat_id=user_id, text=message)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to notify user %s: %s", user_id, exc)


async def handle_admin_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    parts = data.split(":")
    if len(parts) < 4:
        await query.answer("Некорректные данные", show_alert=True)
        return

    action = parts[1]
    try:
        payment_id = int(parts[2])
        user_id = int(parts[3])
    except ValueError:
        await query.answer("Некорректные данные", show_alert=True)
        return

    if action not in {"confirm", "decline"}:
        await query.answer()
        return

    admin_id = update.effective_user.id if update.effective_user else None
    if admin_id is None:
        await query.answer("Не удалось определить администратора", show_alert=True)
        return

    client = _get_api_client()
    try:
        if action == "confirm":
            response = await client.confirm_payment(payment_id, admin_id)
        else:
            response = await client.decline_payment(payment_id, admin_id)
    except CollectorAPIError as exc:
        logger.error("Admin payment action failed: %s", exc)
        await query.answer("Ошибка сервиса", show_alert=True)
        return

    meta = response.get("meta", {}) if isinstance(response, dict) else {}
    result = meta.get("result", "ok")
    await _update_admin_message(update, _build_admin_status_line(action, result))
    await _notify_user(context, user_id, _build_user_notification(action, payment_id, result))
    await query.answer("Готово")
