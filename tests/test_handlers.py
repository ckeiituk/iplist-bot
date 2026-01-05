"""
Tests for handlers module.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestBaseHandlers:
    """Tests for base command handlers."""
    
    @pytest.mark.asyncio
    async def test_start_command(self, mock_update, mock_context):
        """Test /start command sends welcome message."""
        from bot.handlers.base import start
        
        await start(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Главное меню" in call_args
    
    @pytest.mark.asyncio
    async def test_help_command(self, mock_update, mock_context):
        """Test /help command sends help message."""
        from bot.handlers.base import help_command
        
        await help_command(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "/start" in call_args
        assert "/add" in call_args


class TestDomainHandlers:
    """Tests for domain-related handlers."""
    
    def test_clean_domain(self):
        """Test domain cleaning utility."""
        from bot.handlers.domain import _clean_domain
        
        assert _clean_domain("https://www.Example.COM/") == "example.com"
        assert _clean_domain("HTTP://test.org") == "test.org"
        assert _clean_domain("www.site.net") == "site.net"
        assert _clean_domain("plain.com") == "plain.com"
    
    @pytest.mark.asyncio
    async def test_add_domain_manual_missing_args(self, mock_update, mock_context):
        """Test /add with missing arguments shows usage."""
        from bot.handlers.domain import add_domain_manual
        
        mock_context.args = ["only_domain"]  # Missing category
        
        await add_domain_manual(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Использование" in call_args
    
    @pytest.mark.asyncio
    async def test_add_domain_manual_invalid_category(self, mock_update, mock_context):
        """Test /add with invalid category shows error."""
        from bot.handlers.domain import add_domain_manual
        
        mock_context.args = ["example.com", "invalid_category"]
        
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text = AsyncMock(return_value=status_msg)
        
        with patch("bot.handlers.domain._github_client") as mock_gh:
            mock_gh.get_categories = AsyncMock(return_value=["games", "social"])
            
            await add_domain_manual(mock_update, mock_context)
            
            # Should show error about invalid category
            edit_calls = status_msg.edit_text.call_args_list
            last_call = edit_calls[-1][0][0]
            assert "не найдена" in last_call or "Категория" in last_call


class TestCommonHandlers:
    """Tests for common handler utilities."""
    
    @pytest.mark.asyncio
    async def test_send_log_report_skips_without_channel(self, mock_bot):
        """Test that log report is skipped when no channel configured."""
        from bot.handlers.common import send_log_report
        
        with patch("bot.handlers.common.settings") as mock_settings:
            mock_settings.channel_id = None
            
            user = MagicMock()
            user.username = "test"
            user.id = 123
            
            await send_log_report(
                mock_bot, user, "example.com", "games", ["1.2.3.4"], [], "http://url"
            )
            
            mock_bot.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_log_report_with_topic(self, mock_bot):
        """Test log report includes topic when configured."""
        from bot.handlers.common import send_log_report
        
        with patch("bot.handlers.common.settings") as mock_settings:
            mock_settings.channel_id = -100123
            mock_settings.topic_id = 42
            
            user = MagicMock()
            user.username = "testuser"
            user.id = 123
            user.full_name = "Test User"
            
            await send_log_report(
                mock_bot, user, "example.com", "games", ["1.2.3.4"], [], "http://url"
            )
            
            mock_bot.send_message.assert_called_once()
            call_kwargs = mock_bot.send_message.call_args[1]
            assert call_kwargs["message_thread_id"] == 42


class TestMenuHandlers:
    """Tests for menu handlers."""

    @pytest.mark.asyncio
    async def test_menu_callback_help(self, mock_update, mock_context):
        """Help callback should route to help view."""
        from bot.handlers.menu import handle_menu_callback

        mock_update.callback_query = MagicMock()
        mock_update.callback_query.data = "menu:help"
        mock_update.callback_query.answer = AsyncMock()

        with patch("bot.handlers.menu.show_main_menu", new_callable=AsyncMock) as mock_show:
            await handle_menu_callback(mock_update, mock_context)

            mock_show.assert_awaited_once()
            call_kwargs = mock_show.call_args.kwargs
            assert call_kwargs["view"] == "help"

    @pytest.mark.asyncio
    async def test_menu_callback_domain(self, mock_update, mock_context):
        """Domain callback should request a domain message."""
        from bot.handlers.menu import handle_menu_callback

        mock_update.callback_query = MagicMock()
        mock_update.callback_query.data = "menu:domain"
        mock_update.callback_query.answer = AsyncMock()

        with patch("bot.handlers.menu.send_or_edit_primary", new_callable=AsyncMock) as mock_send:
            await handle_menu_callback(mock_update, mock_context)

            mock_send.assert_awaited_once()
            text = mock_send.call_args.kwargs["text"]
            assert "Пришли домен" in text

    @pytest.mark.asyncio
    async def test_menu_callback_section(self, mock_update, mock_context):
        """Section callback should route to LK handler."""
        from bot.handlers.menu import handle_menu_callback

        mock_update.callback_query = MagicMock()
        mock_update.callback_query.data = "menu:balance"
        mock_update.callback_query.answer = AsyncMock()

        with patch("bot.handlers.lk.lk_start", new_callable=AsyncMock) as mock_lk:
            await handle_menu_callback(mock_update, mock_context)

            mock_lk.assert_awaited_once()
            call_kwargs = mock_lk.call_args.kwargs
            assert call_kwargs["section"] == "balance"

    @pytest.mark.asyncio
    async def test_send_payment_request_includes_buttons(self, mock_bot):
        """Test payment request includes admin action buttons."""
        from bot.handlers.common import send_payment_request

        with patch("bot.handlers.common.settings") as mock_settings:
            mock_settings.lk_admin_channel = -100123
            mock_settings.lk_admin_topic = 77

            user = MagicMock()
            user.username = "testuser"
            user.full_name = "Test User"
            user.id = 321

            payment = {
                "id": 55,
                "amount": 10,
                "status": "pending",
                "due_date": "2024-01-01",
                "comment": "Test payment",
            }

            await send_payment_request(mock_bot, user, payment)

            mock_bot.send_message.assert_awaited_once()
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert call_kwargs["message_thread_id"] == 77

            reply_markup = call_kwargs["reply_markup"]
            buttons = reply_markup.inline_keyboard
            assert buttons[0][0].callback_data == "admin_payment:confirm:55:321"
            assert buttons[0][1].callback_data == "admin_payment:decline:55:321"
