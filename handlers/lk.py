"""
User LK (personal dashboard) handlers.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.core.config import settings
from bot.core.exceptions import CollectorAPIError
from bot.core.logging import get_logger
from bot.handlers.common import send_payment_request
from bot.handlers.ui import send_or_edit_primary
from bot.services.collector import CollectorApiClient

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 60.0
_MAX_ITEMS = 8
_MAX_PENDING_ACTIONS = 5
_HISTORY_PAGE_SIZE = 10

_api_client: CollectorApiClient | None = None


def _get_api_client() -> CollectorApiClient:
    global _api_client
    if _api_client is None:
        _api_client = CollectorApiClient(settings.site_api_base_url, settings.site_api_key)
    return _api_client


def _format_amount(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 0.0
    return f"{amount:.2f} ₽"


def _format_date(raw: str | None) -> str:
    if not raw:
        return "—"
    try:
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return raw


def _truncate(text: str, limit: int = 40) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _period_label(period: str) -> str:
    mapping = {
        "monthly": "ежемесячно",
        "semiannual": "раз в полгода",
        "annual": "ежегодно",
        "one-time": "разовый",
    }
    return mapping.get(period, period or "—")


def _summary_title(title: str) -> str:
    icon = "🏠" if title == "Главное меню" else "📊"
    return f"{icon} {title}"


def _build_summary_text(payload: dict[str, Any], *, title: str = "Личный кабинет") -> str:
    user = payload.get("user", {})
    summary = payload.get("summary", {})
    name = user.get("name") or "—"

    pending_count = summary.get("pending_count", 0)
    overdue_count = summary.get("overdue_count", 0)

    lines = [
        _summary_title(title),
        f"👤 {name}",
        f"💳 Баланс: {_format_amount(user.get('balance'))} · Доступно: {_format_amount(summary.get('effective_balance'))}",
        f"📌 К оплате: {_format_amount(summary.get('pending_debt'))}",
        f"🔁 Подписки/мес: {_format_amount(summary.get('monthly_subscriptions_total'))}",
        f"💸 Займы: {_format_amount(summary.get('loan_total'))}",
        f"🧾 Платежи: ожидают {pending_count} · просрочено {overdue_count}",
    ]
    return "\n".join(lines)


def _build_balance_text(payload: dict[str, Any]) -> str:
    user = payload.get("user", {})
    summary = payload.get("summary", {})
    balance = user.get("balance")
    effective_balance = summary.get("effective_balance")
    pending_debt = summary.get("pending_debt")

    lines = [
        "💳 Баланс",
        f"На счету: {_format_amount(balance)}",
        f"К оплате: {_format_amount(pending_debt)}",
        f"Доступно: {_format_amount(effective_balance)}",
    ]
    return "\n".join(lines)


def _build_history_text(history_payload: dict[str, Any]) -> str:
    transactions = history_payload.get("transactions") or []
    total = history_payload.get("total", 0)
    page = history_payload.get("page", 1)
    total_pages = history_payload.get("total_pages", 0)

    if not transactions:
        return "История операций пуста."

    header = f"🧾 История операций (стр. {page}/{total_pages or 1})"
    lines = [header]
    for item in transactions:
        direction = item.get("type")
        emoji = "💰" if direction == "income" else "💸"
        raw_amount = item.get("amount") or 0
        try:
            amount_value = float(raw_amount)
        except (TypeError, ValueError):
            amount_value = 0.0
        sign = "+" if direction == "income" else "-"
        amount = _format_amount(abs(amount_value))
        date = _format_date(item.get("date"))
        description = _truncate(item.get("description") or "Операция", 48)
        lines.append(f"{emoji} {sign}{amount} • {date} • {description}")

    if total and total > len(transactions):
        lines.append(f"Всего операций: {total}")

    return "\n".join(lines)


def _build_subscriptions_text(payload: dict[str, Any]) -> str:
    subscriptions = payload.get("subscriptions") or []
    if not subscriptions:
        return "Подписок нет."

    lines = ["🔁 Подписки"]
    for item in subscriptions[:_MAX_ITEMS]:
        name = item.get("name") or "—"
        amount = _format_amount(item.get("amount"))
        period = _period_label(item.get("period"))
        due = _format_date(item.get("next_due_date"))
        paused = " (приост.)" if item.get("is_paused") else ""
        lines.append(f"• {name} — {amount} • {period} • след. {due}{paused}")
    if len(subscriptions) > _MAX_ITEMS:
        lines.append(f"…и еще {len(subscriptions) - _MAX_ITEMS}")
    return "\n".join(lines)


def _build_loans_text(payload: dict[str, Any]) -> str:
    loans = payload.get("loans") or []
    # Filter out closed loans
    active_loans = [loan for loan in loans if not loan.get("is_paused")]
    
    if not active_loans:
        return "Займов нет."

    lines = ["💸 Займы"]
    for item in active_loans[:_MAX_ITEMS]:
        name = item.get("name") or "—"
        amount = _format_amount(item.get("amount"))
        due = _format_date(item.get("next_due_date"))
        lines.append(f"• {name} — {amount} • {due}")
    if len(active_loans) > _MAX_ITEMS:
        lines.append(f"…и еще {len(active_loans) - _MAX_ITEMS}")
    return "\n".join(lines)


def _status_label(raw: str | None) -> str:
    mapping = {
        "pending": "ожидает",
        "paid": "оплачен",
        "overdue": "просрочен",
        "cancelled": "отменен",
    }
    return mapping.get((raw or "").lower(), raw or "—")


def _build_payments_text(payload: dict[str, Any]) -> str:
    payments = payload.get("payments") or {}
    pending = payments.get("pending") or []
    recent = payments.get("recent") or []

    lines = []
    if pending:
        lines.append("⏳ Ожидают оплаты")
        for item in pending[:_MAX_ITEMS]:
            payment_id = item.get('id')
            amount = _format_amount(item.get("amount"))
            due = _format_date(item.get("due_date"))
            comment = _truncate(item.get("comment") or "Платеж", 50)
            
            lines.append(f"#{payment_id} • {amount}")
            lines.append(f"  📅 {due} • {comment}")
            
        if len(pending) > _MAX_ITEMS:
            lines.append(f"…и еще {len(pending) - _MAX_ITEMS}")
    else:
        lines.append("⏳ Ожидающих платежей нет.")

    if recent:
        lines.append("")
        lines.append("✅ Последние платежи")
        for item in recent[:_MAX_ITEMS]:
            payment_id = item.get('id')
            amount = _format_amount(item.get("amount"))
            paid_at = _format_date(item.get("paid_at") or item.get("created_at"))
            comment = _truncate(item.get("comment") or "Платеж", 50)
            
            lines.append(f"#{payment_id} • {amount}")
            lines.append(f"  📅 {paid_at} • {comment}")
            
        if len(recent) > _MAX_ITEMS:
            lines.append(f"…и еще {len(recent) - _MAX_ITEMS}")

    return "\n".join(lines)


def _build_nav_keyboard(
    section: str,
    payload: dict[str, Any],
    *,
    history_payload: dict[str, Any] | None = None,
) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🏠 Главная", callback_data="menu:main")],
        [
            InlineKeyboardButton("🧾 Платежи", callback_data="lk:payments"),
            InlineKeyboardButton("📊 История", callback_data="lk:history:1"),
        ],
        [
            InlineKeyboardButton("🔁 Подписки", callback_data="lk:subscriptions"),
            InlineKeyboardButton("💸 Займы", callback_data="lk:loans"),
        ],
    ]

    if section == "history" and history_payload:
        nav_row = []
        page = history_payload.get("page", 1)
        if history_payload.get("has_prev"):
            nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"lk:history:{page - 1}"))
        if history_payload.get("has_next"):
            nav_row.append(InlineKeyboardButton("➡️", callback_data=f"lk:history:{page + 1}"))
        if nav_row:
            buttons.append(nav_row)

    if section == "payments":
        pending = (payload.get("payments") or {}).get("pending") or []
        for item in pending[:_MAX_PENDING_ACTIONS]:
            payment_id = item.get("id")
            if payment_id is None:
                continue
            buttons.append([
                InlineKeyboardButton(f"Оплатил #{payment_id}", callback_data=f"lk:paid:{payment_id}")
            ])

    return InlineKeyboardMarkup(buttons)


def _select_section_text(
    section: str,
    payload: dict[str, Any],
    *,
    history_payload: dict[str, Any] | None = None,
) -> str:
    if section == "subscriptions":
        return _build_subscriptions_text(payload)
    if section == "payments":
        return _build_payments_text(payload)
    if section == "loans":
        return _build_loans_text(payload)
    if section == "balance":
        return _build_balance_text(payload)
    if section == "history" and history_payload is not None:
        return _build_history_text(history_payload)
    return _build_summary_text(payload)


def build_menu_summary_text(payload: dict[str, Any]) -> str:
    return _build_summary_text(payload, title="Главное меню")


async def fetch_lk_payload(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    return await _fetch_payload(update, context, force_refresh=force_refresh)


def _get_cached_payload(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    cached = context.user_data.get("lk_payload")
    ts = context.user_data.get("lk_payload_ts")
    if not cached or not ts:
        return None
    if time.time() - ts > _CACHE_TTL_SECONDS:
        return None
    return cached


def _store_payload(context: ContextTypes.DEFAULT_TYPE, payload: dict[str, Any]) -> None:
    context.user_data["lk_payload"] = payload
    context.user_data["lk_payload_ts"] = time.time()


def _get_cached_transactions(context: ContextTypes.DEFAULT_TYPE, page: int) -> dict[str, Any] | None:
    cache = context.user_data.get("lk_transactions_cache") or {}
    cached = cache.get(page)
    if not cached:
        return None
    payload, ts = cached
    if time.time() - ts > _CACHE_TTL_SECONDS:
        return None
    return payload


def _store_transactions(context: ContextTypes.DEFAULT_TYPE, page: int, payload: dict[str, Any]) -> None:
    cache = context.user_data.get("lk_transactions_cache") or {}
    cache[page] = (payload, time.time())
    context.user_data["lk_transactions_cache"] = cache


async def _fetch_transactions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    page: int,
    force_refresh: bool,
) -> dict[str, Any]:
    if not force_refresh:
        cached = _get_cached_transactions(context, page)
        if cached:
            return cached

    client = _get_api_client()
    payload = await client.get_lk_transactions(
        update.effective_user,
        page=page,
        page_size=_HISTORY_PAGE_SIZE,
    )
    _store_transactions(context, page, payload)
    return payload


async def _fetch_payload(update: Update, context: ContextTypes.DEFAULT_TYPE, *, force_refresh: bool) -> dict[str, Any]:
    if not force_refresh:
        cached = _get_cached_payload(context)
        if cached:
            return cached

    try:
        client = _get_api_client()
        payload = await client.get_lk_payload(update.effective_user)
        _store_payload(context, payload)
        return payload
    except CollectorAPIError as exc:
        logger.error("LK fetch failed: %s", exc)
        raise


async def lk_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    section: str = "summary",
    page: int = 1,
    force_refresh: bool = False,
) -> None:
    """Entry point for LK commands and button navigation."""
    try:
        payload = await _fetch_payload(update, context, force_refresh=force_refresh)
    except CollectorAPIError:
        await update.effective_message.reply_text(
            "Сервис ЛК пока недоступен. Попробуй позже или напиши админу."
        )
        return

    history_payload = None
    if section == "history":
        try:
            history_payload = await _fetch_transactions(
                update,
                context,
                page=page,
                force_refresh=force_refresh,
            )
        except CollectorAPIError:
            history_payload = {
                "transactions": [],
                "page": page,
                "total_pages": 0,
                "total": 0,
                "has_prev": False,
                "has_next": False,
            }

    text = _select_section_text(section, payload, history_payload=history_payload)
    keyboard = _build_nav_keyboard(section, payload, history_payload=history_payload)
    context.user_data["lk_section"] = section
    if section == "history":
        context.user_data["lk_history_page"] = page
    await send_or_edit_primary(update, context, text=text, reply_markup=keyboard)


async def handle_lk_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle LK inline button callbacks."""
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    await query.answer()

    if data.startswith("lk:paid:"):
        await _handle_payment_request(update, context, data)
        return

    if data.startswith("lk:history"):
        parts = data.split(":")
        page = 1
        if len(parts) >= 3:
            try:
                page = int(parts[2])
            except ValueError:
                page = 1
        await lk_start(update, context, section="history", page=page)
        return

    if data.startswith("lk:"):
        section = data.split(":", 1)[1] or "summary"
        await lk_start(update, context, section=section)


async def _handle_payment_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
) -> None:
    query = update.callback_query
    if not query:
        return

    try:
        payment_id = int(data.split(":")[-1])
    except ValueError:
        await query.answer("Некорректный платеж", show_alert=True)
        return

    try:
        payload = await _fetch_payload(update, context, force_refresh=False)
    except CollectorAPIError:
        await query.answer("Сервис ЛК недоступен", show_alert=True)
        return

    pending = (payload.get("payments") or {}).get("pending") or []
    payment = next((item for item in pending if item.get("id") == payment_id), None)
    if not payment:
        try:
            payload = await _fetch_payload(update, context, force_refresh=True)
            pending = (payload.get("payments") or {}).get("pending") or []
            payment = next((item for item in pending if item.get("id") == payment_id), None)
        except CollectorAPIError:
            payment = None

    if not payment:
        await query.answer("Платеж не найден или уже закрыт", show_alert=True)
        return

    await send_payment_request(context.bot, update.effective_user, payment)
    await query.answer("Заявка отправлена админу")
    await query.message.reply_text("Заявка на подтверждение оплаты отправлена админу.")
