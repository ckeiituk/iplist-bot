#!/usr/bin/env python3
"""
Telegram bot for automating site additions to iplist GitHub repository.
Modularized version.
"""

import sys
import logging
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Import modules
from config import TG_TOKEN
from handlers.telegram import start, help_command, add_domain_manual, handle_message
from handlers.webhook import start_webhook_server

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    if not TG_TOKEN:
        logger.error("TG_TOKEN not set!")
        sys.exit(1)
        
    # Build Telegram App
    application = Application.builder().token(TG_TOKEN).build()
    
    # Add Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_domain_manual))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start Webhook Server (Background task)
    webhook_task = asyncio.create_task(start_webhook_server())
    
    # Start Bot
    logger.info("Starting bot...")
    
    # Run bot polling
    # We use stop_signals=None because we handle cleanup via asyncio.run/finally implicitly or via OS signals
    # But Application.run_polling is blocking. So we need to ensure webhook runs.
    # Fortunately, run_polling is async aware if we used the async updater logic, 
    # but the recommended way for modern ptb + background tasks is: 
    # use `await application.initialize()`, `await application.start()`, `await application.updater.start_polling()`
    # OR just pass allowed_updates to run_polling and let the loop run.
    # However, create_task works fine before a blocking compatible run call IF it uses the same loop.
    # application.run_polling() creates its own loop? No, usually it uses the current one if called inside async def.
    # Let's verify PTB docs mental model:
    # "If you use asyncio.run(main()), use application.run_polling() inside."
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Keep running until cancelled
    # We await the webhook task too, or just wait forever
    logger.info("Both services are running.")
    
    try:
        # Wait until the updater stops (it won't unless signal)
        # But updater.start_polling is non-blocking (it starts a task).
        pass
    except Exception:
        pass
        
    # We need a forever loop here because start_polling is essentially backgrounded tasks now?
    # No, start_polling starts the fetching task.
    # So we need to keep main alive.
    stop_signal = asyncio.Event()
    await stop_signal.wait()

    # Graceful shutdown (if we ever reach here)
    await application.updater.stop()
    await application.stop()
    await application.shutdown()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
