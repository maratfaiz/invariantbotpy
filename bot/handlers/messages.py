from telegram import Update
from telegram.ext import ContextTypes


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if not message or not message.text:
        return

    if chat.type != chat.PRIVATE:
        moderator = context.bot_data["moderator"]
        deleted = await moderator.handle_message(update, context)
        if deleted:
            return

    bot_username = context.bot_data.get("bot_username")
    mentioned = bool(bot_username) and f"@{bot_username.lower()}" in message.text.lower()
    is_reply_to_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == context.bot.id
    )

    if chat.type != chat.PRIVATE and not (mentioned or is_reply_to_bot):
        return

    text = message.text
    if bot_username:
        text = text.replace(f"@{bot_username}", "").strip()
    if not text:
        return

    ollama_client = context.bot_data["ollama"]
    await context.bot.send_chat_action(chat.id, "typing")
    answer = await ollama_client.chat_reply(
        [
            {"role": "system", "content": "Ты дружелюбный ассистент в Telegram-чате, отвечай кратко на русском."},
            {"role": "user", "content": text},
        ]
    )
    await message.reply_text(answer)
