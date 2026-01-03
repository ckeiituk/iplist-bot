"""
Webhook server setup.
"""

from aiohttp import web

from bot.core.logging import get_logger
from bot.webhooks.github import handle_workflow_run

logger = get_logger(__name__)


async def start_webhook_server(host: str = "0.0.0.0", port: int = 8081) -> None:
    """
    Start the webhook server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
    """
    app = web.Application()
    app.router.add_post("/webhook/github", handle_workflow_run)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    logger.info(f"Webhook server started on {host}:{port}")
