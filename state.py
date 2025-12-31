# Storage for pending builds: {commit_sha: {user_id, domain, chat_id, message_id, bot_instance?}}
# We will use this module to share state between Webhook and Telegram handlers.
pending_builds = {}
