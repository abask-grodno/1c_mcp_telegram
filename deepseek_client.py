# deepseek_client.py
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

class DeepSeekClient:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_response(self, messages: list, model: str = "deepseek-chat"):
        """
        Отправляет запрос к DeepSeek API и возвращает ответ.
        messages: список сообщений в формате [{"role": "user", "content": "..."}]
        model: название модели (по умолчанию 'deepseek-chat')
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500
        }
        try:
            response = await self.client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Ошибка при обращении к DeepSeek: {e}"
            