"""
Base Telegram command handlers.
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.menu import show_main_menu


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await show_main_menu(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await show_main_menu(update, context, view="help")
