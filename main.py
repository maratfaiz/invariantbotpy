import logging

from dotenv import load_dotenv
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters

from bot.config import load_settings
from bot.handlers import commands as cmd
from bot.handlers.errors import error_handler
from bot.handlers.messages import on_message
from bot.moderation import Moderator
from bot.ollama_client import OllamaClient
from bot.storage import Storage

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    me = await application.bot.get_me()
    application.bot_data["bot_username"] = me.username
    logger.info("Bot started as @%s", me.username)


def main() -> None:
    settings = load_settings()

    storage = Storage(settings.db_path)
    storage.init_db()

    ollama_client = OllamaClient(settings.ollama_host, settings.ollama_model)
    moderator = Moderator(
        storage, ollama_client, settings.default_warn_limit, settings.default_mute_minutes
    )

    application = ApplicationBuilder().token(settings.bot_token).post_init(post_init).build()
    application.bot_data["storage"] = storage
    application.bot_data["ollama"] = ollama_client
    application.bot_data["moderator"] = moderator
    application.bot_data["settings"] = settings

    application.add_handler(CommandHandler("start", cmd.start_command))
    application.add_handler(CommandHandler("help", cmd.help_command))
    application.add_handler(CommandHandler("connect", cmd.connect_command))
    application.add_handler(CommandHandler("disconnect", cmd.disconnect_command))
    application.add_handler(CommandHandler("automod", cmd.automod_command))
    application.add_handler(CommandHandler("rules", cmd.rules_command))
    application.add_handler(CommandHandler("status", cmd.status_command))
    application.add_handler(CommandHandler("warns", cmd.warns_command))
    application.add_handler(CommandHandler("resetwarns", cmd.resetwarns_command))
    application.add_handler(CommandHandler("mute", cmd.mute_command))
    application.add_handler(CommandHandler("unmute", cmd.unmute_command))
    application.add_handler(CommandHandler("kick", cmd.kick_command))
    application.add_handler(CommandHandler("ban", cmd.ban_command))
    application.add_handler(CommandHandler("ask", cmd.ask_command))
    application.add_handler(CommandHandler("setmodel", cmd.setmodel_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=["message", "chat_member"])


if __name__ == "__main__":
    main()
