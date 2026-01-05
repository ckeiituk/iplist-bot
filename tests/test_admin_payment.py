"""
Tests for admin payment handlers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_admin_payment_confirm_notifies_user(mock_context):
    """Confirm button should call API and notify the user."""
    from bot.handlers.admin_payment import handle_admin_payment_callback

    update = MagicMock()
    update.effective_user.id = 777
    query = MagicMock()
    query.data = "admin_payment:confirm:55:123"
    query.answer = AsyncMock()
    query.message.text = "Request"
    query.edit_message_text = AsyncMock()
    update.callback_query = query

    mock_context.bot.send_message = AsyncMock()

    with patch("bot.handlers.admin_payment._get_api_client") as mock_get_client:
        client = MagicMock()
        client.confirm_payment = AsyncMock(return_value={"meta": {"result": "paid"}})
        mock_get_client.return_value = client

        await handle_admin_payment_callback(update, mock_context)

    client.confirm_payment.assert_awaited_once_with(55, 777)
    mock_context.bot.send_message.assert_awaited_once()
    call_kwargs = mock_context.bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == 123

    query.answer.assert_awaited()
    query.edit_message_text.assert_awaited()
    edited_text = query.edit_message_text.call_args.kwargs["text"]
    assert "Подтверждено" in edited_text


@pytest.mark.asyncio
async def test_admin_payment_decline_notifies_user(mock_context):
    """Decline button should call API and notify the user."""
    from bot.handlers.admin_payment import handle_admin_payment_callback

    update = MagicMock()
    update.effective_user.id = 999
    query = MagicMock()
    query.data = "admin_payment:decline:88:456"
    query.answer = AsyncMock()
    query.message.text = "Request"
    query.edit_message_text = AsyncMock()
    update.callback_query = query

    mock_context.bot.send_message = AsyncMock()

    with patch("bot.handlers.admin_payment._get_api_client") as mock_get_client:
        client = MagicMock()
        client.decline_payment = AsyncMock(return_value={"meta": {"result": "declined"}})
        mock_get_client.return_value = client

        await handle_admin_payment_callback(update, mock_context)

    client.decline_payment.assert_awaited_once_with(88, 999)
    mock_context.bot.send_message.assert_awaited_once()
    call_kwargs = mock_context.bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == 456

    query.answer.assert_awaited()
    query.edit_message_text.assert_awaited()
    edited_text = query.edit_message_text.call_args.kwargs["text"]
    assert "Отклонено" in edited_text


@pytest.mark.asyncio
async def test_admin_payment_invalid_payload(mock_context):
    """Invalid callback payload should alert the admin."""
    from bot.handlers.admin_payment import handle_admin_payment_callback

    update = MagicMock()
    update.effective_user.id = 111
    query = MagicMock()
    query.data = "admin_payment:confirm"
    query.answer = AsyncMock()
    update.callback_query = query

    await handle_admin_payment_callback(update, mock_context)

    query.answer.assert_awaited_once_with("Некорректные данные", show_alert=True)


@pytest.mark.asyncio
async def test_admin_payment_unknown_action(mock_context):
    """Unknown action should no-op with answer."""
    from bot.handlers.admin_payment import handle_admin_payment_callback

    update = MagicMock()
    update.effective_user.id = 111
    query = MagicMock()
    query.data = "admin_payment:noop:1:2"
    query.answer = AsyncMock()
    update.callback_query = query

    await handle_admin_payment_callback(update, mock_context)

    query.answer.assert_awaited_once()
