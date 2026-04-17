# mcp_client_1c.py
import os
import itertools
import httpx
from dotenv import load_dotenv

load_dotenv()

class MCPClient1C:
    def __init__(self):
        self.base_url = os.getenv("MCP_SERVER_URL")
        self.client = httpx.AsyncClient(timeout=30.0)
        self._request_ids = itertools.count(1)
        self._initialized = False

    async def _send_request(self, method: str, params: dict = None, retries: int = 2):
        """Отправляет базовый JSON-RPC запрос к MCP-серверу."""
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._request_ids),
            "method": method,
            "params": params or {}
        }

        if not self.base_url:
            raise RuntimeError("MCP_SERVER_URL не задан в переменных окружения")

        last_error = None
        for _ in range(retries + 1):
            try:
                response = await self.client.post(self.base_url, json=payload)
                response.raise_for_status()
                data = response.json()
                if "error" in data:
                    err = data["error"]
                    code = err.get("code", "unknown")
                    message = err.get("message", "Неизвестная ошибка MCP")
                    raise RuntimeError(f"MCP error {code}: {message}")
                return data
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                continue
            except Exception as exc:
                raise RuntimeError(f"Ошибка при обращении к MCP-серверу: {exc}") from exc

        raise RuntimeError(f"MCP-сервер недоступен после повторных попыток: {last_error}")

    async def initialize(self):
        """
        Инициализирует MCP-сессию (если сервер поддерживает initialize).
        Если метод не поддерживается на сервере, продолжаем работу без фатальной ошибки.
        """
        if self._initialized:
            return
        try:
            await self._send_request("initialize", {"client": "telegram-bot"})
        except RuntimeError:
            # Некоторые совместимые JSON-RPC серверы не требуют initialize.
            pass
        self._initialized = True

    async def get_tools(self):
        """Получает список доступных инструментов (tools) от сервера 1С."""
        await self.initialize()
        return await self._send_request("tools/list")

    async def call_tool(self, tool_name: str, arguments: dict):
        """Вызывает конкретный инструмент на сервере 1С."""
        await self.initialize()
        params = {
            "name": tool_name,
            "arguments": arguments
        }
        return await self._send_request("tools/call", params)

    async def close(self):
        """Корректно закрывает HTTP-клиент."""
        await self.client.aclose()

