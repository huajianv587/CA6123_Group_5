import json
from typing import Any, Optional

from openai import OpenAI

from shared.config import get_settings


class OpenAIClient:
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[OpenAI] = None
        self.provider = self._provider()
        self.chat_model = self._chat_model()
        api_key = self._api_key()
        base_url = self._base_url()
        if api_key:
            kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = OpenAI(**kwargs)

    @property
    def available(self) -> bool:
        return self._client is not None

    def _provider(self) -> str:
        if self.settings.deepseek_key:
            return "deepseek"
        return (self.settings.llm_provider or "openai").lower()

    def _api_key(self) -> Optional[str]:
        if self.provider == "deepseek":
            return self.settings.deepseek_key or self.settings.openai_api_key
        return self.settings.openai_api_key

    def _base_url(self) -> Optional[str]:
        if self.provider == "deepseek":
            return self.settings.llm_base_url or "https://api.deepseek.com"
        return self.settings.llm_base_url

    def _chat_model(self) -> str:
        if self.settings.llm_chat_model:
            return self.settings.llm_chat_model
        if self.provider == "deepseek":
            return "deepseek-v4-flash"
        return self.settings.openai_chat_model

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
                model=self.chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=500,
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except Exception:
            return None

    def embed(self, text: str) -> Optional[list[float]]:
        if not self._client or self.provider == "deepseek":
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
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content
        except Exception:
            return None
