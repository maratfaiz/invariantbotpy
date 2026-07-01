import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    ollama_host: str
    ollama_model: str
    superadmin_ids: set[int]
    db_path: str
    default_warn_limit: int
    default_mute_minutes: int


def load_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Create a bot via @BotFather and put the "
            "token into the TELEGRAM_BOT_TOKEN environment variable (or .env file)."
        )

    superadmin_ids = {
        int(chunk)
        for chunk in os.environ.get("SUPERADMIN_IDS", "").replace(" ", "").split(",")
        if chunk
    }

    return Settings(
        bot_token=token,
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.1"),
        superadmin_ids=superadmin_ids,
        db_path=os.environ.get("DB_PATH", "data/bot.db"),
        default_warn_limit=int(os.environ.get("WARN_LIMIT", "3")),
        default_mute_minutes=int(os.environ.get("MUTE_MINUTES", "60")),
    )
