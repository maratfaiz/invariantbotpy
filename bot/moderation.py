import logging
from datetime import datetime, timedelta, timezone

from telegram import ChatPermissions, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from .ollama_client import OllamaClient
from .storage import Storage

logger = logging.getLogger(__name__)


class Moderator:
    """Runs incoming group messages through the Ollama model and applies
    the moderation action (delete/warn/mute/kick/ban) it recommends."""

    def __init__(self, storage: Storage, ollama_client: OllamaClient, warn_limit: int, mute_minutes: int):
        self.storage = storage
        self.ollama = ollama_client
        self.warn_limit = warn_limit
        self.mute_minutes = mute_minutes

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Returns True if the triggering message was deleted."""
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if not message or not chat or not user or not message.text:
            return False

        settings = await self.storage.get_chat(chat.id)
        if not settings["automod_enabled"]:
            return False

        try:
            member = await context.bot.get_chat_member(chat.id, user.id)
            if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                return False
        except Exception:
            logger.exception("Failed to fetch chat member status for %s in %s", user.id, chat.id)

        result = await self.ollama.moderate(message.text, settings["rules"])
        if not result.get("violation"):
            return False

        action = result.get("action", "none")
        reason = result.get("reason", "") or result.get("category", "")
        return await self._apply_action(action, update, context, reason)

    async def _apply_action(
        self, action: str, update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str
    ) -> bool:
        chat = update.effective_chat
        user = update.effective_user
        message = update.effective_message

        try:
            if action == "delete":
                await message.delete()
                await self._notify(
                    context, chat.id,
                    f"🗑 Сообщение от {user.mention_html()} удалено ИИ-модератором.\nПричина: {reason}",
                )
                return True

            if action == "warn":
                count = await self.storage.add_warning(chat.id, user.id)
                await self._notify(
                    context, chat.id,
                    f"⚠️ Предупреждение {user.mention_html()} ({count}/{self.warn_limit}).\nПричина: {reason}",
                )
                if count >= self.warn_limit:
                    await self._mute(context, chat.id, user.id, self.mute_minutes)
                    await self.storage.reset_warnings(chat.id, user.id)
                    await self._notify(
                        context, chat.id,
                        f"🔇 {user.mention_html()} замьючен на {self.mute_minutes} мин. "
                        "за превышение лимита предупреждений.",
                    )
                return False

            if action == "mute":
                await message.delete()
                await self._mute(context, chat.id, user.id, self.mute_minutes)
                await self._notify(
                    context, chat.id,
                    f"🔇 {user.mention_html()} замьючен на {self.mute_minutes} мин.\nПричина: {reason}",
                )
                return True

            if action == "kick":
                await message.delete()
                await context.bot.ban_chat_member(chat.id, user.id)
                await context.bot.unban_chat_member(chat.id, user.id)
                await self._notify(
                    context, chat.id, f"👢 {user.mention_html()} удалён из чата.\nПричина: {reason}"
                )
                return True

            if action == "ban":
                await message.delete()
                await context.bot.ban_chat_member(chat.id, user.id)
                await self._notify(
                    context, chat.id, f"⛔ {user.mention_html()} заблокирован.\nПричина: {reason}"
                )
                return True
        except Exception:
            logger.exception("Failed to apply moderation action %s", action)

        return False

    async def _mute(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, minutes: int) -> None:
        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        await context.bot.restrict_chat_member(
            chat_id, user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )

    @staticmethod
    async def _notify(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> None:
        await context.bot.send_message(chat_id, text, parse_mode="HTML")
