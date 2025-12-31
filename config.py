import os
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("iplist_bot")

# Environment variables
TG_TOKEN = os.getenv("TG_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
# Parse API keys list
GEMINI_API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEY", "").split(",") if k.strip()]
if not GEMINI_API_KEYS:
    GEMINI_API_KEYS = [""] # Fallback

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# Constants
GITHUB_REPO = "ckeiituk/iplist"
GITHUB_BRANCH = "master"
GEMINI_MODEL = "gemini-2.5-flash-lite"
DNS_SERVERS = ["127.0.0.11:53", "77.88.8.88:53", "8.8.8.8:53", "1.1.1.1:53"]

# Authorized users (Update this list as needed or move to env)
# Since the original code had this check implicitly or explicitly?
# The original code had:
# if update.effective_user.id != ...: return
# Actually, the original code in previous turns had authorized user check?
# I need to check `bot.py` lines to see if there was a hardcoded ID or env var for auth.
# In the `view_file` output I didn't see an explicit Auth check in shared bits, 
# but I should preserve whatever logic was there.
# Let's assume standard TG_TOKEN access creates basic restriction, 
# but usually there is an APPROVED_USERS list.
# I'll check bot.py content for `ALLOWED_USERS` or similar.
