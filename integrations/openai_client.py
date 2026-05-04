import json
from typing import Any, Optional

from openai import OpenAI

from shared.config import get_settings


class OpenAIClient:
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[OpenAI] = None
        if self.settings.openai_api_key:
            self._client = OpenAI(api_key=self.settings.openai_api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    def classify_intent(self, text: str) -> Optional[dict[str, Any]]:
        if not self._client:
            return None
        prompt = (
            "Classify this Chinese ecommerce customer-service message. "
            "Return strict JSON with keys: intent(order|logistics|refund|complaint|unknown), "
            "confidence(0-1), entities(object), emotion(object with level low|medium|high). "
            f"Message: {text}"
        )
        try:
            resp = self._client.chat.completions.create(
                model=self.settings.openai_chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except Exception:
            return None

    def embed(self, text: str) -> Optional[list[float]]:
        if not self._client:
            return None
        try:
            resp = self._client.embeddings.create(
                model=self.settings.openai_embedding_model,
                input=text,
            )
            return resp.data[0].embedding
        except Exception:
            return None

    def short_answer(self, system: str, user: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.settings.openai_chat_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content
        except Exception:
            return None
