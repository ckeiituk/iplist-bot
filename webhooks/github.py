"""
GitHub webhook handler for workflow_run events.
"""

import hmac
import hashlib
from aiohttp import web

from bot.core.config import settings
from bot.core.logging import get_logger
from bot.state.builds import pending_builds

logger = get_logger(__name__)


async def handle_workflow_run(request: web.Request) -> web.Response:
    """Handle GitHub App webhook events for workflow_run."""
    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        return web.Response(status=401, text="No signature")
    
    body = await request.read()
    
    if settings.webhook_secret:
        secret = settings.webhook_secret.encode()
        expected_signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return web.Response(status=401, text="Invalid signature")
    
    event = request.headers.get("X-GitHub-Event")
    if event != "workflow_run":
        return web.Response(status=200, text="Ignored event")
    
    try:
        payload = await request.json()
        workflow_run = payload.get("workflow_run", {})
        status = workflow_run.get("status")
        conclusion = workflow_run.get("conclusion")
        head_sha = workflow_run.get("head_sha")
        
        # Only interested in completed workflows
        if status != "completed":
            return web.Response(status=200, text="Not completed yet")
        
        if conclusion == "success":
            # Notify all pending builds on success
            to_notify = pending_builds.get_all_shas()
            for sha in to_notify:
                await notify_user_success(sha)
                
        elif conclusion == "cancelled":
            # Keep pending, wait for next success
            logger.info(f"Build cancelled for {head_sha}. Waiting for next success.")
            
        elif conclusion == "failure":
            if head_sha in pending_builds:
                await notify_user_failure(head_sha)
        
        return web.Response(status=200, text="Processed")
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500, text="Internal Server Error")


async def notify_user_success(sha: str) -> None:
    """Notify user about successful build."""
    build = pending_builds.pop(sha)
    if not build:
        return
    
    try:
        kwargs = {
            "chat_id": build.chat_id,
            "text": (
                f"✅ **Сборка завершена успешно!**\n"
                f"Сайт `{build.domain}` добавлен в списки.\n\n"
                f"🔄 **Совет:** Обновите профиль в VPN клиенте, чтобы изменения вступили в силу."
            ),
            "parse_mode": "Markdown",
        }
        if build.message_thread_id:
            kwargs["message_thread_id"] = build.message_thread_id
        
        await build.bot.send_message(**kwargs)
    except Exception as e:
        logger.error(f"Failed to send success msg: {e}")


async def notify_user_failure(sha: str) -> None:
    """Notify user about failed build."""
    build = pending_builds.pop(sha)
    if not build:
        return
    
    try:
        kwargs = {
            "chat_id": build.chat_id,
            "text": f"❌ **Сборка не удалась!**\nЧто-то пошло не так при добавлении `{build.domain}`.",
            "parse_mode": "Markdown",
        }
        if build.message_thread_id:
            kwargs["message_thread_id"] = build.message_thread_id
        
        await build.bot.send_message(**kwargs)
    except Exception as e:
        logger.error(f"Failed to send failure msg: {e}")
