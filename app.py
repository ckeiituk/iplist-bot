"""
Application factory and main entry point.
"""

import sys
import asyncio
from telegram.ext import Application

from bot.core.config import settings
from bot.core.logging import setup_logging, get_logger
from bot.handlers import register_handlers
from bot.webhooks.server import start_webhook_server

# Initialize logging
setup_logging()
logger = get_logger(__name__)


async def create_app() -> Application:
    """Create and configure the Telegram Application."""
    if not settings.tg_token:
        logger.error("TG_TOKEN not set!")
        sys.exit(1)
    
    application = Application.builder().token(settings.tg_token).build()
    register_handlers(application)
    
    return application


async def main() -> None:
    """Main application entry point."""
    logger.info("Starting bot...")
    
    # Create Telegram app
    application = await create_app()
    
    # Start webhook server (background task)
    webhook_task = asyncio.create_task(start_webhook_server())
    
    # Initialize and start bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    logger.info("Both services are running.")
    
    # Keep running until cancelled
    stop_signal = asyncio.Event()
    try:
        await stop_signal.wait()
    except asyncio.CancelledError:
        pass
    finally:
        # Graceful shutdown
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
