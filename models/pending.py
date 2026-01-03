"""
Data model for pending build tracking.
"""

from dataclasses import dataclass
from telegram import Bot


@dataclass
class PendingBuild:
    """Represents a pending GitHub Actions build for a domain."""
    
    user_id: int
    domain: str
    chat_id: int
    bot: Bot
    message_thread_id: int | None = None
