"""
Telegram handlers registration.
"""

from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters


def register_handlers(app: Application) -> None:
    """Register all Telegram handlers with the application."""
    from bot.handlers.admin_payment import handle_admin_payment_callback
    from bot.handlers.admin_reminder import handle_admin_reminder
    from bot.handlers.base import start, help_command
    from bot.handlers.domain import add_domain_manual, handle_message, handle_domain_callback
    from bot.handlers.lk import lk_start, handle_lk_callback
    from bot.handlers.menu import show_main_menu, handle_menu_callback
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", show_main_menu))
    app.add_handler(CommandHandler("lk", lk_start))
    app.add_handler(CommandHandler("me", lk_start))
    app.add_handler(CommandHandler("add", add_domain_manual))
    app.add_handler(CommandHandler("remind", handle_admin_reminder))
    app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(handle_lk_callback, pattern=r"^lk:"))
    app.add_handler(CallbackQueryHandler(handle_domain_callback, pattern=r"^domain:"))
    app.add_handler(CallbackQueryHandler(handle_admin_payment_callback, pattern=r"^admin_payment:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
