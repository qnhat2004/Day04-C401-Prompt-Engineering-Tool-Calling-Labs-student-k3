from __future__ import annotations

import json
import os
from typing import Any

from providers.base import ModelResponse, ToolCall


class CerebrasProvider:
    """Cerebras API provider with normalized tool_calls output."""

    def __init__(
        self,
        *,
        api_key_env: str = "CEREBRAS_API_KEY",
        default_model: str = "llama3.1-8b",
    ) -> None:
        self.api_key_env = api_key_env
        self.default_model = default_model

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        tool_choice: Any | None = None,
    ) -> ModelResponse:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {self.api_key_env}")

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url="https://api.cerebras.ai/v1")
        except ImportError as exc:
            raise RuntimeError("Install openai package first: pip install openai") from exc

        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        import time
        max_retries = 5
        resp = None
        for attempt in range(max_retries):
            try:
                resp = client.chat.completions.create(**kwargs)
                break
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "rate" in err_str.lower() or "limit" in err_str.lower():
                    if attempt < max_retries - 1:
                        sleep_sec = 5 * (attempt + 1)
                        print(f"[Cerebras 429 Rate Limit] Pausing {sleep_sec}s before retry {attempt + 1}/{max_retries}...", flush=True)
                        time.sleep(sleep_sec)
                        continue
                raise exc

        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        for call in getattr(msg, "tool_calls", None) or []:
            args = json.loads(call.function.arguments or "{}")
            calls.append(ToolCall(name=call.function.name, args=args))
        return ModelResponse(text=msg.content, tool_calls=calls, raw=resp)
