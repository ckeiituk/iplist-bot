"""Main menu handlers."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.handlers.ui import send_or_edit_primary


def _build_main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("Личный кабинет", callback_data="menu:lk")],
        [
            InlineKeyboardButton("Баланс", callback_data="menu:balance"),
            InlineKeyboardButton("История", callback_data="menu:history"),
        ],
        [
            InlineKeyboardButton("Подписки", callback_data="menu:subscriptions"),
            InlineKeyboardButton("Платежи", callback_data="menu:payments"),
        ],
        [
            InlineKeyboardButton("Займы", callback_data="menu:loans"),
            InlineKeyboardButton("Добавить домен", callback_data="menu:domain"),
        ],
        [InlineKeyboardButton("Помощь", callback_data="menu:help")],
    ]
    return InlineKeyboardMarkup(buttons)


def _build_help_text() -> str:
    return (
        "Команды:\n"
        "/lk - Личный кабинет\n"
        "/me - Личный кабинет\n"
        "/start - Главное меню\n"
        "/menu - Главное меню\n"
        "/add <домен> <категория> - Ручное добавление домена\n\n"
        "Можно просто отправить домен — я уточню действие."
    )


def _build_menu_text() -> str:
    return (
        "Привет! Главное меню.\n"
        "Выбери раздел ниже, я обновлю сообщение без спама."
    )


async def show_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    view: str = "main",
) -> None:
    text = _build_menu_text()
    if view == "help":
        text = _build_help_text()

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

    if data == "menu:domain":
        await send_or_edit_primary(
            update,
            context,
            text="Пришли домен сообщением, я уточню действие.",
            reply_markup=_build_main_menu_keyboard(),
        )
        return

    if data.startswith("menu:"):
        section = data.split(":", 1)[1]
        if section in {"lk", "balance", "history", "subscriptions", "payments", "loans"}:
            from bot.handlers.lk import lk_start

            target_section = "summary" if section == "lk" else section
            await lk_start(update, context, section=target_section)
            return

    await show_main_menu(update, context)
