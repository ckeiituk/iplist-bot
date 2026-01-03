"""
Telegram handlers registration.
"""

from telegram.ext import Application, CommandHandler, MessageHandler, filters


def register_handlers(app: Application) -> None:
    """Register all Telegram handlers with the application."""
    from bot.handlers.base import start, help_command
    from bot.handlers.domain import add_domain_manual, handle_message
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_domain_manual))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
