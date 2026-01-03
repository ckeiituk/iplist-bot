"""
Base Telegram command handlers.
"""

from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "Привет! Отправь мне домен сайта, "
        "и я добавлю его в правила VPN клиента."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        "Команды:\n"
        "/start - Начать работу\n"
        "/add <домен> <категория> - Ручное добавление домена в категорию\n"
        "Либо просто отправь домен сообщением, и я попробую определить категорию сам."
    )
