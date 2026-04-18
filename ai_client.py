# ai_client.py
import os
import httpx
from dotenv import load_dotenv

load_dotenv()


class AIClient:
    def __init__(self):
        self.provider = os.getenv("AI_MODEL_PROVIDER", "deepseek").lower()
        self.api_key = os.getenv("AI_MODEL_API_KEY")
        self.base_url = os.getenv("AI_MODEL_BASE_URL", "https://api.deepseek.com/v1/chat/completions")
        self.model_name = os.getenv("AI_MODEL_NAME", "deepseek-chat")
        self.client = httpx.AsyncClient(timeout=120.0)
        
        # Provider-specific configurations
        self._provider_configs = {
            "deepseek": {
                "auth_header": "Authorization",
                "auth_format": "Bearer {}",
                "default_base_url": "https://api.deepseek.com/v1/chat/completions",
                "default_model": "deepseek-chat",
            },
            "openai": {
                "auth_header": "Authorization",
                "auth_format": "Bearer {}",
                "default_base_url": "https://api.openai.com/v1/chat/completions",
                "default_model": "gpt-4o",
            },
            "anthropic": {
                "auth_header": "x-api-key",
                "auth_format": "{}",
                "default_base_url": "https://api.anthropic.com/v1/messages",
                "default_model": "claude-3-5-sonnet-20241022",
            },
            "google": {
                "auth_header": "Authorization",
                "auth_format": "Bearer {}",
                "default_base_url": "https://generativelanguage.googleapis.com/v1beta/models",
                "default_model": "gemini-1.5-pro",
            },
        }
        
        # Apply provider defaults if not explicitly set
        if self.provider in self._provider_configs:
            config = self._provider_configs[self.provider]
            if not self.base_url or self.base_url == "":
                self.base_url = config["default_base_url"]
            if not self.model_name or self.model_name == "":
                self.model_name = config["default_model"]
        
        self._validate_config()

    def _validate_config(self):
        """Validate configuration and log warnings."""
        import logging
        logger = logging.getLogger("ai_client")
        
        if not self.api_key:
            logger.warning("AI_MODEL_API_KEY не задан в переменных окружения")
        
        logger.info(
            "AI client initialized: provider=%s, model=%s, base_url=%s",
            self.provider,
            self.model_name,
            self.base_url,
        )

    def _build_headers(self):
        """Build headers based on provider."""
        if self.provider in self._provider_configs:
            config = self._provider_configs[self.provider]
            auth_header = config["auth_header"]
            auth_format = config["auth_format"]
            
            headers = {
                "Content-Type": "application/json",
            }
            
            if self.api_key:
                headers[auth_header] = auth_format.format(self.api_key)
            
            # Provider-specific headers
            if self.provider == "anthropic":
                headers["anthropic-version"] = "2023-06-01"
            elif self.provider == "google":
                # Google uses different endpoint structure
                pass
            
            return headers
        
        # Fallback for unknown providers
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        return headers

    def _build_payload(self, messages: list, max_tokens: int, temperature: float):
        """Build request payload based on provider."""
        if self.provider == "anthropic":
            # Anthropic API format
            return {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        elif self.provider == "google":
            # Google Gemini API format
            return {
                "contents": [
                    {
                        "parts": [
                            {"text": msg["content"]}
                            for msg in messages
                            if msg["role"] in ["user", "assistant"]
                        ]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature,
                }
            }
        else:
            # OpenAI-compatible format (DeepSeek, OpenAI, etc.)
            return {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

    def _extract_response(self, data: dict):
        """Extract response text from provider-specific response format."""
        if self.provider == "anthropic":
            # Anthropic response format
            if "content" in data and len(data["content"]) > 0:
                return data["content"][0]["text"]
            raise ValueError("Invalid Anthropic response format")
        
        elif self.provider == "google":
            # Google Gemini response format
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if len(parts) > 0 and "text" in parts[0]:
                        return parts[0]["text"]
            raise ValueError("Invalid Google Gemini response format")
        
        else:
            # OpenAI-compatible response format
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            raise ValueError("Invalid OpenAI-compatible response format")

    async def get_response(
        self,
        messages: list,
        model: str = None,
        *,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ):
        """
        Отправляет запрос к AI API и возвращает ответ.
        messages: список сообщений в формате [{"role": "user", "content": "..."}]
        model: название модели (переопределяет AI_MODEL_NAME)
        """
        import logging
        logger = logging.getLogger("ai_client")
        
        # Use provided model or default
        model_to_use = model or self.model_name
        
        headers = self._build_headers()
        payload = self._build_payload(messages, max_tokens, temperature)
        
        # Update model in payload if provided
        if model_to_use:
            payload["model"] = model_to_use
        
        try:
            logger.debug(
                "AI request -> provider=%s, model=%s, messages=%d",
                self.provider,
                model_to_use,
                len(messages),
            )
            
            response = await self.client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            logger.debug(
                "AI response <- provider=%s, model=%s, status=%s",
                self.provider,
                model_to_use,
                response.status_code,
            )
            
            return self._extract_response(data)
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "AI API HTTP error: status=%s, response=%s",
                e.response.status_code,
                e.response.text[:500],
            )
            raise RuntimeError(f"Ошибка AI API (HTTP {e.response.status_code}): {e.response.text[:200]}")
        except Exception as e:
            logger.exception("AI API request failed")
            raise RuntimeError(f"Ошибка при обращении к AI API: {e}") from e

    async def close(self):
        """Корректно закрывает HTTP-клиент."""
        await self.client.aclose()