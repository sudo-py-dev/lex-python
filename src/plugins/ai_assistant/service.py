from typing import Any

import httpx
from loguru import logger


class AIServiceError(Exception):
    pass


class AIService:
    PROVIDERS = {
        "openai": "https://api.openai.com/v1/chat/completions",
        "deepseek": "https://api.deepseek.com/v1/chat/completions",
        "groq": "https://api.groq.com/openai/v1/chat/completions",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    }

    @staticmethod
    async def call_ai(
        p: str,
        k: str,
        m: str,
        sys: str | None,
        inst: str | None,
        msgs: list[dict[str, Any]],
        fmt: dict | None = None,
    ) -> str:
        if p in AIService.PROVIDERS:
            return await AIService._call_openai_compatible(
                AIService.PROVIDERS[p], k, m, sys, inst, msgs, fmt
            )
        if p in ("claude", "anthropic"):
            return await AIService._call_anthropic(k, m, sys, inst, msgs)
        raise AIServiceError(f"Unsupported provider: {p}")

    @staticmethod
    async def validate_api(p: str, k: str, m: str) -> bool:
        try:
            await AIService.call_ai(p, k, m, "Validator", None, [{"role": "user", "content": "hi"}])
            return True
        except Exception as e:
            logger.error(f"API Validation failed ({p}): {e}")
            return False

    @staticmethod
    async def _call_openai_compatible(
        url: str,
        k: str,
        m: str,
        sys: str | None,
        inst: str | None,
        msgs: list[dict[str, Any]],
        fmt: dict | None = None,
    ) -> str:
        headers = {"Authorization": f"Bearer {k}", "Content-Type": "application/json"}
        payload_msgs = []
        if sys:
            payload_msgs.append({"role": "system", "content": sys})
        if inst:
            payload_msgs.append({"role": "system", "content": inst})
        payload_msgs.extend(msgs)

        payload = {"model": m, "messages": payload_msgs, "temperature": 0.7}
        if fmt:
            payload["response_format"] = fmt

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                err_body = e.response.text
                if e.response.status_code == 413 or "request_too_large" in err_body.lower():
                    logger.warning(f"Payload too large: {url}")
                raise AIServiceError(f"API Error ({e.response.status_code}): {err_body}") from e
            except Exception as e:
                raise AIServiceError(f"Request failed: {str(e)}") from e

    @staticmethod
    async def _call_anthropic(
        k: str, m: str, sys: str | None, inst: str | None, msgs: list[dict[str, str]]
    ) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": k,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {"model": m, "max_tokens": 1024, "messages": msgs, "temperature": 0.7}
        if sys or inst:
            payload["system"] = "\n\n".join(filter(None, [sys, inst]))

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()["content"][0]["text"]
            except Exception as e:
                raise AIServiceError(f"Anthropic Error: {str(e)}") from e
