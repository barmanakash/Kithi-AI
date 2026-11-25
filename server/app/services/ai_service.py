"""Centralised local-AI service (Ollama only).

- One shared model, one request at a time (a lock serialises inference for 8 GB machines).
- Structured JSON output validated against a Pydantic model, with one corrective retry.
- Explicit, typed errors. There is deliberately NO fallback to any external AI provider.
"""
import json
import logging
import re
import threading
from functools import lru_cache
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

logger = logging.getLogger("kithi.ai")

T = TypeVar("T", bound=BaseModel)


class AIServiceError(Exception):
    status_code = 502


class AIUnavailableError(AIServiceError):
    status_code = 503


class AIBusyError(AIServiceError):
    status_code = 503


class AIResponseError(AIServiceError):
    status_code = 502


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise json.JSONDecodeError("Expected a JSON object", text, 0)
    return data


class AIService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._lock = threading.Lock()
        self._client = httpx.Client(
            base_url=self._settings.ollama_base_url,
            timeout=httpx.Timeout(self._settings.ollama_timeout_seconds, connect=5.0),
        )

    def close(self) -> None:
        self._client.close()

    def status(self) -> dict:
        model = self._settings.ollama_model
        info = {
            "endpoint": self._settings.ollama_base_url,
            "model": model,
            "reachable": False,
            "model_available": False,
            "installed_models": [],
            "message": "",
        }
        try:
            response = self._client.get("/api/tags", timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            info["message"] = f"Ollama is not reachable ({type(exc).__name__}). Start it with: ollama serve"
            return info

        names = [m.get("name", "") for m in response.json().get("models", [])]
        info["reachable"] = True
        info["installed_models"] = names
        info["model_available"] = model in names or f"{model}:latest" in names
        info["message"] = (
            "Ready"
            if info["model_available"]
            else f"Model not installed. Run: ollama pull {model}"
        )
        return info

    def _chat(self, messages: list[dict], json_mode: bool) -> str:
        payload = {
            "model": self._settings.ollama_model,
            "messages": messages,
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.2, "num_ctx": self._settings.ollama_num_ctx},
        }
        if json_mode:
            payload["format"] = "json"

        if not self._lock.acquire(timeout=self._settings.ollama_timeout_seconds):
            raise AIBusyError("The local AI model is busy with another request. Try again shortly.")
        try:
            try:
                response = self._client.post("/api/chat", json=payload)
            except httpx.ConnectError:
                raise AIUnavailableError(
                    f"Cannot reach Ollama at {self._settings.ollama_base_url}. Start it with: ollama serve"
                )
            except httpx.TimeoutException:
                raise AIServiceError("The local AI model timed out. Try a shorter input.")
        finally:
            self._lock.release()

        if response.status_code == 404:
            raise AIUnavailableError(
                f"Model '{self._settings.ollama_model}' is not installed. Run: ollama pull {self._settings.ollama_model}"
            )
        if response.status_code >= 400:
            raise AIServiceError(f"Ollama returned HTTP {response.status_code}")
        try:
            return response.json()["message"]["content"]
        except (KeyError, ValueError):
            raise AIResponseError("Ollama returned an unexpected response format")

    def generate_structured(self, system: str, prompt: str, model_cls: type[T], max_retries: int = 1) -> T:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        last_error = "unknown error"
        for attempt in range(max_retries + 1):
            raw = self._chat(messages, json_mode=True)
            try:
                return model_cls.model_validate(_extract_json(raw))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)[:300]
                logger.warning("AI output invalid (attempt %d): %s", attempt + 1, last_error)
                messages = messages + [
                    {"role": "assistant", "content": raw[:2000]},
                    {
                        "role": "user",
                        "content": "Your previous reply was not valid for the required JSON format. "
                        f"Problem: {last_error}. Reply again with ONLY the corrected JSON object.",
                    },
                ]
        raise AIResponseError(f"The local model did not return valid structured output: {last_error}")


@lru_cache
def get_ai_service() -> AIService:
    return AIService()
