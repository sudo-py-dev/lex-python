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
        provider: str,
        api_key: str,
        model_id: str,
        system_prompt: str | None,
        custom_instruction: str | None,
        messages: list[dict[str, Any]],
        response_format: dict | None = None,
    ) -> str:
        """
        Unified call mechanism using the OpenAI Chat Completion protocol.
        Anthropic is handled via its native protocol as it differs significantly.
        """
        if provider in AIService.PROVIDERS:
            return await AIService._call_openai_compatible(
                AIService.PROVIDERS[provider],
                api_key,
                model_id,
                system_prompt,
                custom_instruction,
                messages,
                response_format,
            )
        elif provider == "claude" or provider == "anthropic":
            return await AIService._call_anthropic(
                api_key, model_id, system_prompt, custom_instruction, messages
            )
        else:
            raise AIServiceError(f"Unsupported provider: {provider}")

    @staticmethod
    async def validate_api(provider: str, api_key: str, model_id: str) -> bool:
        """
        Validates the API key and model by making a minimal request.
        """
        try:
            test_msg = [{"role": "user", "content": "hi"}]
            await AIService.call_ai(provider, api_key, model_id, "Validator", None, test_msg)
            return True
        except (httpx.RequestError, ValueError) as e:
            logger.error(f"API Validation failed for {provider}: {e}")
            return False

    @staticmethod
    async def _call_openai_compatible(
        url: str,
        api_key: str,
        model_id: str,
        system_prompt: str | None,
        custom_instruction: str | None,
        messages: list[dict[str, Any]],
        response_format: dict | None = None,
    ) -> str:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        if custom_instruction:
            payload_messages.append({"role": "system", "content": custom_instruction})
        payload_messages.extend(messages)

        payload = {"model": model_id, "messages": payload_messages, "temperature": 0.7}
        if response_format:
            payload["response_format"] = response_format

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                error_body = e.response.text
                status = e.response.status_code
                body_l = error_body.lower()
                if status == 413 or "request_too_large" in body_l:
                    logger.warning(f"API payload too large from {url}: {error_body}")
                else:
                    logger.debug(f"API error from {url}: {error_body}")
                raise AIServiceError(f"API Error ({e.response.status_code}): {error_body}") from e
            except (httpx.RequestError, ValueError, KeyError) as e:
                logger.debug(f"Request failed for {url}: {e}")
                raise AIServiceError(f"Request failed: {str(e)}") from e

    @staticmethod
    async def _call_anthropic(
        api_key: str,
        model_id: str,
        system_prompt: str | None,
        custom_instruction: str | None,
        messages: list[dict[str, str]],
    ) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": model_id,
            "max_tokens": 1024,
            "messages": messages,
            "temperature": 0.7,
        }
        if system_prompt or custom_instruction:
            parts = []
            if system_prompt:
                parts.append(system_prompt)
            if custom_instruction:
                parts.append(custom_instruction)
            payload["system"] = "\n\n".join(parts)

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["content"][0]["text"]
            except httpx.HTTPStatusError as e:
                error_body = e.response.text
                logger.debug(f"Anthropic API error: {error_body}")
                raise AIServiceError(f"Anthropic API Error ({e.response.status_code})") from e
            except (httpx.RequestError, ValueError, KeyError) as e:
                logger.debug(f"Anthropic request failed: {e}")
                raise AIServiceError(str(e)) from e
