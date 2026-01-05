"""
Tests for UI helpers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from telegram.error import BadRequest


@pytest.mark.asyncio
async def test_send_or_edit_primary_edits_callback_message(mock_context):
    """Callback query should edit the existing message and store ids."""
    from bot.handlers.ui import send_or_edit_primary

    update = MagicMock()
    message = MagicMock()
    message.chat_id = 11
    message.message_id = 22
    message.edit_text = AsyncMock()
    query = MagicMock()
    query.message = message

    update.callback_query = query
    update.effective_chat.id = 11
    update.effective_message.reply_text = AsyncMock()

    await send_or_edit_primary(update, mock_context, text="Hello")

    message.edit_text.assert_awaited_once()
    assert mock_context.user_data["primary_message_id"] == 22
    assert mock_context.user_data["primary_chat_id"] == 11


@pytest.mark.asyncio
async def test_send_or_edit_primary_callback_not_modified(mock_context):
    """BadRequest 'message is not modified' should be ignored."""
    from bot.handlers.ui import send_or_edit_primary

    update = MagicMock()
    message = MagicMock()
    message.chat_id = 5
    message.message_id = 9
    message.edit_text = AsyncMock(side_effect=BadRequest("message is not modified"))
    query = MagicMock()
    query.message = message
    update.callback_query = query

    await send_or_edit_primary(update, mock_context, text="Same")

    assert mock_context.user_data["primary_message_id"] == 9
    assert mock_context.user_data["primary_chat_id"] == 5


@pytest.mark.asyncio
async def test_send_or_edit_primary_edits_stored_message(mock_context):
    """Should edit stored primary message when available."""
    from bot.handlers.ui import send_or_edit_primary

    mock_context.user_data["primary_message_id"] = 101
    mock_context.user_data["primary_chat_id"] = 202
    mock_context.bot.edit_message_text = AsyncMock()

    update = MagicMock()
    update.callback_query = None
    update.effective_chat.id = 202
    update.effective_message.reply_text = AsyncMock()

    await send_or_edit_primary(update, mock_context, text="Update")

    mock_context.bot.edit_message_text.assert_awaited_once()
    update.effective_message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_or_edit_primary_sends_new_message(mock_context):
    """Should send a new message when no primary message stored."""
    from bot.handlers.ui import send_or_edit_primary

    update = MagicMock()
    update.callback_query = None
    update.effective_chat.id = 303
    sent = MagicMock()
    sent.chat_id = 303
    sent.message_id = 404
    update.effective_message.reply_text = AsyncMock(return_value=sent)

    await send_or_edit_primary(update, mock_context, text="Fresh")

    update.effective_message.reply_text.assert_awaited_once()
    assert mock_context.user_data["primary_message_id"] == 404
    assert mock_context.user_data["primary_chat_id"] == 303
