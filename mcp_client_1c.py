# mcp_client_1c.py
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

class MCPClient1C:
    def __init__(self):
        self.base_url = os.getenv("MCP_SERVER_URL")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _send_request(self, method: str, params: dict = None):
        """Отправляет базовый JSON-RPC запрос к MCP-серверу."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        try:
            response = await self.client.post(self.base_url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Ошибка при обращении к MCP-серверу: {e}"}

    async def get_tools(self):
        """Получает список доступных инструментов (tools) от сервера 1С."""
        return await self._send_request("tools/list")

    async def call_tool(self, tool_name: str, arguments: dict):
        """Вызывает конкретный инструмент на сервере 1С."""
        params = {
            "name": tool_name,
            "arguments": arguments
        }
        return await self._send_request("tools/call", params)

