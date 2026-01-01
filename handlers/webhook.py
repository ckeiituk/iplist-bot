import hmac
import hashlib
import logging
import asyncio
from aiohttp import web
from config import WEBHOOK_SECRET
from state import pending_builds

logger = logging.getLogger(__name__)

async def handle_workflow_run(request):
    """Handle GitHub App webhook events for workflow_run."""
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        return web.Response(status=401, text="No signature")
    
    body = await request.read()
    
    if WEBHOOK_SECRET:
        secret = WEBHOOK_SECRET.encode()
        expected_signature = 'sha256=' + hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return web.Response(status=401, text="Invalid signature")

    event = request.headers.get('X-GitHub-Event')
    if event != "workflow_run":
        return web.Response(status=200, text="Ignored event")
    
    try:
        payload = await request.json()
        workflow_run = payload.get("workflow_run", {})
        status = workflow_run.get("status")
        conclusion = workflow_run.get("conclusion")
        head_sha = workflow_run.get("head_sha")
        
        # Only interest in completed workflows
        if status != "completed":
             return web.Response(status=200, text="Not completed yet")

        # Logic for Smart Waiting (Batched Notifications)
        # 1. Successful build
        if conclusion == "success":
            # Notify pending builds associated with this SHA
            if head_sha in pending_builds:
                await notify_user_success(head_sha)
            
            # CRITICAL: Also notify all OTHER pending builds that were 'cancelled' or waiting
            # Because a successful build usually includes previous commits.
            # We assume linear history for simplicity.
            # We will notify ALL pending builds!
            # (Or valid strategy: only notify those that are older? 
            # For simplicity, if a build succeeds, we consider the repo "stable" and notify everyone waiting).
            
            # Make a copy of keys to iterate safe
            to_notify = list(pending_builds.keys())
            for sha in to_notify:
                # Notify everyone as success
                await notify_user_success(sha)
            
        # 2. Cancelled build
        elif conclusion == "cancelled":
            # Do NOT notify user. Just keep them in pending_builds.
            logger.info(f"Build cancelled for {head_sha}. Waiting for next success.")
            
        # 3. Failed build
        elif conclusion == "failure":
             if head_sha in pending_builds:
                 await notify_user_failure(head_sha)
        
        return web.Response(status=200, text="Processed")
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500, text="Internal Server Error")

async def notify_user_success(sha):
    info = pending_builds.pop(sha, None)
    if not info: return
    
    bot = info['bot']
    chat_id = info['chat_id']
    domain = info['domain']
    message_thread_id = info.get('message_thread_id')
    
    try:
        kwargs = {
            "chat_id": chat_id,
            "text": (
                f"✅ **Сборка завершена успешно!**\n"
                f"Сайт `{domain}` добавлен в списки.\n\n"
                f"🔄 **Совет:** Обновите профиль в VPN клиенте, чтобы изменения вступили в силу."
            ),
            "parse_mode": "Markdown"
        }
        if message_thread_id:
            kwargs["message_thread_id"] = message_thread_id
            
        await bot.send_message(**kwargs)
    except Exception as e:
        logger.error(f"Failed to send success msg: {e}")

async def notify_user_failure(sha):
    info = pending_builds.pop(sha, None)
    if not info: return
    
    bot = info['bot']
    chat_id = info['chat_id']
    domain = info['domain']
    message_thread_id = info.get('message_thread_id')
    
    try:
         kwargs = {
            "chat_id": chat_id,
            "text": f"❌ **Сборка не удалась!**\nЧто-то пошло не так при добавлении `{domain}`.",
            "parse_mode": "Markdown"
         }
         if message_thread_id:
            kwargs["message_thread_id"] = message_thread_id
            
         await bot.send_message(**kwargs)
    except Exception as e:
        logger.error(f"Failed to send failure msg: {e}")

async def start_webhook_server():
    app = web.Application()
    app.router.add_post('/webhook/github', handle_workflow_run)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8081)
    await site.start()
    logger.info("Webhook server started on port 8081")
    # Return runner to keep reference if needed, but for now we just start it
