"""Main menu handlers."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from bot.core.config import settings
from bot.core.exceptions import CollectorAPIError
from bot.handlers.lk import build_menu_summary_text, fetch_lk_payload
from bot.handlers.ui import send_or_edit_primary


def _build_main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = []

    if settings.site_webapp_url:
        buttons.append(
            [InlineKeyboardButton("📱 Открыть ЛК", web_app=WebAppInfo(url=settings.site_webapp_url))]
        )

    buttons.extend([
        [
            InlineKeyboardButton("🧾 Платежи", callback_data="menu:payments"),
            InlineKeyboardButton("🔁 Подписки", callback_data="menu:subscriptions"),
        ],
        [
            InlineKeyboardButton("💸 Займы", callback_data="menu:loans"),
            InlineKeyboardButton("📊 История", callback_data="menu:history"),
        ],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="menu:help")],
    ])
    return InlineKeyboardMarkup(buttons)


def _build_help_text() -> str:
    return (
        "💡 Что я умею:\n\n"
        "• Просто пришли домен — я сам добавлю его\n"
        "• Напиши \"платежи\", \"баланс\", \"подписки\" — покажу детали\n"
        "• Используй кнопки ниже для быстрого доступа\n\n"
        "Команды:\n"
        "/start или /menu - Главное меню\n"
        "/lk или /me - Личный кабинет"
    )


def _build_menu_text() -> str:
    return (
        "🏠 Главное меню\n"
        "Выбери раздел ниже, я обновлю сообщение без спама."
    )


async def _build_menu_summary(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    force_refresh: bool,
) -> str:
    if not settings.site_api_base_url or not settings.site_api_key:
        return _build_menu_text()
    payload = await fetch_lk_payload(update, context, force_refresh=force_refresh)
    return build_menu_summary_text(payload)


async def show_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    view: str = "main",
    force_refresh: bool = False,
) -> None:
    text = _build_menu_text()
    if view == "help":
        text = _build_help_text()
    elif view == "main":
        try:
            text = await _build_menu_summary(update, context, force_refresh=force_refresh)
        except CollectorAPIError:
            text = _build_menu_text() + "\n\nЛК временно недоступен."

    if view == "help":
        text = _build_help_text()
        # Show simplified keyboard with back button on help screen
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]
        ])
    else:
        keyboard = _build_main_menu_keyboard()
        
    await send_or_edit_primary(update, context, text=text, reply_markup=keyboard)


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    await query.answer()

    if data == "menu:help":
        await show_main_menu(update, context, view="help")
        return

    if data.startswith("menu:"):
        section = data.split(":", 1)[1]
        if section in {"lk", "balance", "history", "subscriptions", "payments", "loans"}:
            from bot.handlers.lk import lk_start

            target_section = "summary" if section == "lk" else section
            await lk_start(update, context, section=target_section)
            return

    await show_main_menu(update, context)
