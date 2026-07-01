import json
import logging
import re

import ollama

logger = logging.getLogger(__name__)

MODERATION_SYSTEM_PROMPT = (
    "Ты — модератор группового чата в Telegram. Тебе дают правила чата и текст "
    "сообщения пользователя. Оцени, нарушает ли сообщение правила (спам, реклама, "
    "оскорбления, разжигание ненависти, флуд, NSFW и т.п.). "
    "Ответь СТРОГО в формате JSON без пояснений вокруг:\n"
    '{"violation": true|false, "category": "строка", '
    '"action": "none|delete|warn|mute|kick|ban", "reason": "краткое объяснение на русском"}\n'
    "Если сообщение безобидное — violation=false, action=none. "
    "Действие выбирай соразмерно тяжести: лёгкое нарушение — warn, спам/флуд — delete или mute, "
    "оскорбления/угрозы — mute или kick, серьёзные или повторные нарушения — ban."
)

FALLBACK_RESULT = {"violation": False, "category": "error", "action": "none", "reason": ""}


class OllamaClient:
    def __init__(self, host: str, model: str):
        self._client = ollama.AsyncClient(host=host)
        self.model = model

    async def chat_reply(self, messages: list[dict], model: str | None = None) -> str:
        response = await self._client.chat(model=model or self.model, messages=messages)
        return response["message"]["content"].strip()

    async def moderate(self, text: str, rules: str) -> dict:
        user_prompt = (
            f"Правила чата:\n{rules or 'Стандартные правила приличия и запрет спама.'}\n\n"
            f"Сообщение пользователя:\n{text}"
        )
        try:
            response = await self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": MODERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                format="json",
            )
            return self._parse_json(response["message"]["content"])
        except Exception:
            logger.exception("Ollama moderation call failed")
            return dict(FALLBACK_RESULT)

    @staticmethod
    def _parse_json(content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            logger.warning("Could not parse moderation response as JSON: %r", content)
            return dict(FALLBACK_RESULT)
