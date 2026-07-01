from datetime import datetime, timedelta, timezone

from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from ..permissions import is_chat_admin

HELP_TEXT = (
    "🤖 <b>ИИ-бот для управления Telegram-чатами (на базе Ollama)</b>\n\n"
    "Добавьте бота в группу администратором с правами удаления сообщений, "
    "блокировки и ограничения участников, затем выполните /connect.\n\n"
    "<b>Команды администратора чата:</b>\n"
    "/connect — подключить чат к ИИ-модерации\n"
    "/disconnect — отключить ИИ-модерацию\n"
    "/automod on|off — включить/выключить авто-модерацию\n"
    "/rules &lt;текст&gt; — задать правила чата для ИИ\n"
    "/status — показать текущие настройки чата\n"
    "/warns — предупреждения пользователя (ответом на сообщение)\n"
    "/resetwarns — сбросить предупреждения (ответом на сообщение)\n"
    "/mute [минуты] — замьютить (ответом на сообщение)\n"
    "/unmute — снять мьют (ответом на сообщение)\n"
    "/kick — выгнать из чата (ответом на сообщение)\n"
    "/ban — забанить (ответом на сообщение)\n"
    "/ask &lt;вопрос&gt; — спросить ИИ напрямую\n\n"
    "В личных сообщениях, а также при упоминании или ответе боту в группе — "
    "просто напишите ему, и он ответит с помощью Ollama."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_html(HELP_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_html(HELP_TEXT)


async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type == chat.PRIVATE:
        await update.effective_message.reply_text("Эта команда используется в группах.")
        return
    if not await is_chat_admin(update, context):
        await update.effective_message.reply_text("Только администратор чата может это сделать.")
        return

    bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
    if not getattr(bot_member, "can_restrict_members", False) or not getattr(
        bot_member, "can_delete_messages", False
    ):
        await update.effective_message.reply_text(
            "Дайте боту права администратора (удаление сообщений, ограничение участников), "
            "затем повторите /connect."
        )
        return

    storage = context.bot_data["storage"]
    await storage.set_connected(chat.id, chat.title or "", True)
    await update.effective_message.reply_text(
        "✅ Чат подключён. ИИ-модерация включена. Настройте правила через /rules <текст>."
    )


async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_chat_admin(update, context):
        await update.effective_message.reply_text("Только администратор чата может это сделать.")
        return
    storage = context.bot_data["storage"]
    await storage.set_automod(update.effective_chat.id, False)
    await update.effective_message.reply_text("ИИ-модерация отключена для этого чата.")


async def automod_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_chat_admin(update, context):
        await update.effective_message.reply_text("Только администратор чата может это сделать.")
        return
    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.effective_message.reply_text("Использование: /automod on|off")
        return
    enabled = context.args[0].lower() == "on"
    storage = context.bot_data["storage"]
    await storage.set_automod(update.effective_chat.id, enabled)
    await update.effective_message.reply_text(f"Авто-модерация {'включена' if enabled else 'выключена'}.")


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_chat_admin(update, context):
        await update.effective_message.reply_text("Только администратор чата может это сделать.")
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.effective_message.reply_text("Использование: /rules <текст правил чата>")
        return
    storage = context.bot_data["storage"]
    await storage.set_rules(update.effective_chat.id, text)
    await update.effective_message.reply_text("Правила чата обновлены.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    storage = context.bot_data["storage"]
    settings = await storage.get_chat(chat.id)
    text = (
        "<b>Настройки чата</b>\n"
        f"Подключён: {'да' if settings['connected'] else 'нет'}\n"
        f"Авто-модерация: {'включена' if settings['automod_enabled'] else 'выключена'}\n"
        f"Правила: {settings['rules'] or '—'}\n"
    )
    await update.effective_message.reply_html(text)


def _target_user(update: Update):
    message = update.effective_message
    if message.reply_to_message:
        return message.reply_to_message.from_user
    return None


async def warns_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = _target_user(update)
    if not target:
        await update.effective_message.reply_text("Ответьте этой командой на сообщение пользователя.")
        return
    storage = context.bot_data["storage"]
    count = await storage.get_warnings(update.effective_chat.id, target.id)
    await update.effective_message.reply_html(f"У {target.mention_html()} предупреждений: {count}")


async def resetwarns_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_chat_admin(update, context):
        await update.effective_message.reply_text("Только администратор чата может это сделать.")
        return
    target = _target_user(update)
    if not target:
        await update.effective_message.reply_text("Ответьте этой командой на сообщение пользователя.")
        return
    storage = context.bot_data["storage"]
    await storage.reset_warnings(update.effective_chat.id, target.id)
    await update.effective_message.reply_html(f"Предупреждения {target.mention_html()} сброшены.")


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_chat_admin(update, context):
        await update.effective_message.reply_text("Только администратор чата может это сделать.")
        return
    target = _target_user(update)
    if not target:
        await update.effective_message.reply_text("Ответьте этой командой на сообщение пользователя.")
        return
    settings = context.bot_data["settings"]
    minutes = (
        int(context.args[0])
        if context.args and context.args[0].isdigit()
        else settings.default_mute_minutes
    )
    until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        target.id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=until,
    )
    await update.effective_message.reply_html(f"🔇 {target.mention_html()} замьючен на {minutes} мин.")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_chat_admin(update, context):
        await update.effective_message.reply_text("Только администратор чата может это сделать.")
        return
    target = _target_user(update)
    if not target:
        await update.effective_message.reply_text("Ответьте этой командой на сообщение пользователя.")
        return
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        target.id,
        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        ),
    )
    await update.effective_message.reply_html(f"🔊 С {target.mention_html()} сняты ограничения.")


async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_chat_admin(update, context):
        await update.effective_message.reply_text("Только администратор чата может это сделать.")
        return
    target = _target_user(update)
    if not target:
        await update.effective_message.reply_text("Ответьте этой командой на сообщение пользователя.")
        return
    chat_id = update.effective_chat.id
    await context.bot.ban_chat_member(chat_id, target.id)
    await context.bot.unban_chat_member(chat_id, target.id)
    await update.effective_message.reply_html(f"👢 {target.mention_html()} удалён из чата.")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_chat_admin(update, context):
        await update.effective_message.reply_text("Только администратор чата может это сделать.")
        return
    target = _target_user(update)
    if not target:
        await update.effective_message.reply_text("Ответьте этой командой на сообщение пользователя.")
        return
    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await update.effective_message.reply_html(f"⛔ {target.mention_html()} заблокирован.")


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.effective_message.reply_text("Использование: /ask <вопрос>")
        return
    ollama_client = context.bot_data["ollama"]
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    answer = await ollama_client.chat_reply(
        [
            {"role": "system", "content": "Ты полезный ассистент, отвечай кратко и по делу на русском."},
            {"role": "user", "content": question},
        ]
    )
    await update.effective_message.reply_text(answer)


async def setmodel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = context.bot_data["settings"]
    if update.effective_user.id not in settings.superadmin_ids:
        await update.effective_message.reply_text("Недостаточно прав.")
        return
    ollama_client = context.bot_data["ollama"]
    if not context.args:
        await update.effective_message.reply_text(f"Текущая модель: {ollama_client.model}")
        return
    ollama_client.model = context.args[0]
    await update.effective_message.reply_text(f"Модель изменена на {context.args[0]}")
