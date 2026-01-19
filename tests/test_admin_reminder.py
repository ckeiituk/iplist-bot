"""
Tests for admin reminder handlers.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_admin_reminder_requires_admin(mock_context, monkeypatch):
    """Non-admin users should be denied."""
    from bot.handlers.admin_reminder import handle_admin_reminder, settings

    update = MagicMock()
    update.effective_user.id = 111
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()

    future = datetime.now() + timedelta(days=1)
    mock_context.args = ["123", future.strftime("%Y-%m-%d"), future.strftime("%H:%M"), "Test"]

    monkeypatch.setattr(settings, "admin_user_ids", "222")

    await handle_admin_reminder(update, mock_context)

    reply_text = update.effective_message.reply_text.call_args.args[0]
    assert "администратор" in reply_text.lower()


@pytest.mark.asyncio
async def test_admin_reminder_schedules_task(mock_context, monkeypatch):
    """Admin can schedule a reminder."""
    from bot.handlers.admin_reminder import handle_admin_reminder, settings

    update = MagicMock()
    update.effective_user.id = 777
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()

    future = datetime.now() + timedelta(days=1)
    mock_context.args = [
        "123456",
        future.strftime("%Y-%m-%d"),
        future.strftime("%H:%M"),
        "Напомнить",
        "про",
        "оплату",
    ]

    monkeypatch.setattr(settings, "admin_user_ids", "777")

    with patch("bot.handlers.admin_reminder._schedule_reminder_task") as mock_schedule:
        await handle_admin_reminder(update, mock_context)

    mock_schedule.assert_called_once()
    reply_text = update.effective_message.reply_text.call_args.args[0]
    assert "Напоминание" in reply_text
