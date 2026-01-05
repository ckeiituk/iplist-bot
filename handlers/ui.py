"""Shared helpers for UI message updates."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

_PRIMARY_MESSAGE_ID_KEY = "primary_message_id"
_PRIMARY_CHAT_ID_KEY = "primary_chat_id"


def store_primary_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int) -> None:
    context.user_data[_PRIMARY_CHAT_ID_KEY] = chat_id
    context.user_data[_PRIMARY_MESSAGE_ID_KEY] = message_id


async def send_or_edit_primary(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit the primary UI message when possible, otherwise send a new one."""
    if update.callback_query and update.callback_query.message:
        message = update.callback_query.message
        try:
            await message.edit_text(text=text, reply_markup=reply_markup)
            store_primary_message(context, message.chat_id, message.message_id)
            return
        except BadRequest as exc:
            if "message is not modified" in str(exc):
                store_primary_message(context, message.chat_id, message.message_id)
                return

    chat = update.effective_chat
    chat_id = chat.id if chat else None
    message_id = context.user_data.get(_PRIMARY_MESSAGE_ID_KEY)
    stored_chat_id = context.user_data.get(_PRIMARY_CHAT_ID_KEY)

    if chat_id and message_id and stored_chat_id == chat_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return
        except BadRequest as exc:
            if "message is not modified" in str(exc):
                return

    if update.effective_message:
        sent = await update.effective_message.reply_text(text, reply_markup=reply_markup)
        store_primary_message(context, sent.chat_id, sent.message_id)
        return

    if chat_id:
        sent = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        store_primary_message(context, sent.chat_id, sent.message_id)
