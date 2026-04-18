# mcp_client_1c.py
import os
import re
import itertools
import json
import logging
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("mcp_client_1c")


def _stringify_mcp_tool_result(result) -> str:
    """Превращает result из tools/call в строку для подстановки в промпт."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if result.get("isError"):
            parts_err = []
            if "content" in result:
                for block in result["content"]:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts_err.append(block.get("text", ""))
            err_text = (
                result.get("error")
                or result.get("message")
                or "\n".join(p for p in parts_err if p)
            )
            if err_text:
                return f"Ошибка 1С/MCP: {err_text}"
        if "content" in result:
            parts = []
            for block in result["content"]:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    else:
                        parts.append(json.dumps(block, ensure_ascii=False))
                else:
                    parts.append(str(block))
            return "\n".join(p for p in parts if p)
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


class MCPClient1C:
    def __init__(self):
        self.base_url = os.getenv("MCP_SERVER_URL")
        self.log_payload_max_len = int(os.getenv("MCP_LOG_PAYLOAD_MAX_LEN", "4000"))
        
        # Basic authentication (optional)
        self.auth_username = os.getenv("MCP_AUTH_USERNAME")
        self.auth_password = os.getenv("MCP_AUTH_PASSWORD")
        self.auth = None
        if self.auth_username and self.auth_password:
            import base64
            auth_str = f"{self.auth_username}:{self.auth_password}"
            auth_bytes = auth_str.encode("utf-8")
            auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")
            self.auth = f"Basic {auth_b64}"
            logger.info("MCP client: Basic authentication enabled for user '%s'", self.auth_username)
        else:
            logger.info("MCP client: No authentication configured")
        
        self.client = httpx.AsyncClient(timeout=120.0)
        self._request_ids = itertools.count(1)
        self._initialized = False
        self.last_call_cache_hit = False
        self.structure_cache_dir = Path("contexts") / "structure"
        self.structure_cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "MCP client initialized: url=%s",
            self.base_url,
        )

    def _structure_cache_path(self, tool_name: str, arguments: dict) -> Optional[Path]:
        """Определяет путь к файлу кэша для структурных инструментов."""

        if tool_name == "list_metadata_objects":
            meta_type = arguments.get("metaType") or "all"
            key = f"list_{meta_type}"
        elif tool_name == "get_metadata_structure":
            meta_type = arguments.get("metaType") or "unknown"
            name = arguments.get("name") or "unnamed"
            key = f"structure_{meta_type}_{name}"
        else:
            return None

        safe_key = re.sub(r"[^\w\-]+", "_", key, flags=re.UNICODE)
        return self.structure_cache_dir / f"{safe_key}.json"

    def _load_structure_cache(self, cache_path: Path) -> tuple[bool, object]:
        if not cache_path.exists():
            return False, None

        try:
            with cache_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            logger.info("Используем кэш структуры: %s", cache_path.name)
            return True, data
        except Exception as exc:
            logger.warning("Не удалось прочитать кэш %s: %s", cache_path, exc)
            return False, None

    def _store_structure_cache(self, cache_path: Path, data: object) -> None:
        try:
            with cache_path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            logger.info("Структура сохранена в кэш: %s", cache_path.name)
        except Exception as exc:
            logger.warning("Не удалось сохранить кэш %s: %s", cache_path, exc)

    def _shorten(self, value) -> str:
        """Ограничивает размер лога, чтобы не захламлять вывод."""
        text = json.dumps(value, ensure_ascii=False, default=str)
        if len(text) <= self.log_payload_max_len:
            return text
        return f"{text[: self.log_payload_max_len]}... <truncated>"

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

        headers = {}
        if self.auth:
            headers["Authorization"] = self.auth

        last_error = None
        for attempt in range(retries + 1):
            try:
                logger.info(
                    "MCP request -> method=%s attempt=%s payload=%s auth=%s",
                    method,
                    f"{attempt + 1}/{retries + 1}",
                    self._shorten(payload),
                    "yes" if self.auth else "no",
                )
                response = await self.client.post(self.base_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "MCP response <- method=%s status=%s body=%s",
                    method,
                    response.status_code,
                    self._shorten(data),
                )
                if "error" in data:
                    err = data["error"]
                    code = err.get("code", "unknown")
                    message = err.get("message", "Неизвестная ошибка MCP")
                    raise RuntimeError(f"MCP error {code}: {message}")
                return data
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                logger.warning(
                    "MCP transport error method=%s attempt=%s error=%s",
                    method,
                    f"{attempt + 1}/{retries + 1}",
                    exc,
                )
                continue
            except Exception as exc:
                logger.exception("MCP request failed method=%s error=%s", method, exc)
                raise RuntimeError(f"Ошибка при обращении к MCP-серверу: {exc}") from exc

        raise RuntimeError(f"MCP-сервер недоступен после повторных попыток: {last_error}")

    async def _send_notification(self, method: str, params: dict = None):
        """JSON-RPC notification (без id) — для notifications/initialized."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        if not self.base_url:
            raise RuntimeError("MCP_SERVER_URL не задан в переменных окружения")
        
        headers = {}
        if self.auth:
            headers["Authorization"] = self.auth
        
        logger.info(
            "MCP notification -> method=%s payload=%s auth=%s",
            method,
            self._shorten(payload),
            "yes" if self.auth else "no",
        )
        response = await self.client.post(self.base_url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(
            "MCP notification ack <- method=%s status=%s",
            method,
            response.status_code,
        )

    async def initialize(self):
        """
        Инициализирует MCP-сессию (если сервер поддерживает initialize).
        Если метод не поддерживается на сервере, продолжаем работу без фатальной ошибки.
        """
        if self._initialized:
            return
        try:
            await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "telegram-1c-bot", "version": "1.0.0"},
                },
            )
            try:
                await self._send_notification("notifications/initialized", {})
            except Exception:
                pass
        except RuntimeError:
            # Упрощённые JSON-RPC шлюзы 1С могут не реализовывать initialize.
            pass
        self._initialized = True

    async def get_tools(self):
        """Получает список доступных инструментов (tools) от сервера 1С."""
        await self.initialize()
        return await self._send_request("tools/list")

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Вызывает инструмент на сервере 1С; возвращает текст результата для ИИ."""
        await self.initialize()

        cache_path = self._structure_cache_path(tool_name, arguments or {})
        self.last_call_cache_hit = False

        if cache_path:
            cached, cached_data = self._load_structure_cache(cache_path)
            if cached:
                logger.info(
                    "MCP cache hit: tool=%s args=%s file=%s",
                    tool_name,
                    arguments,
                    cache_path.name,
                )
                self.last_call_cache_hit = True
                return json.dumps(cached_data, ensure_ascii=False, indent=2)

        params = {
            "name": tool_name,
            "arguments": arguments
        }
        data = await self._send_request("tools/call", params)
        result = data.get("result")

        if cache_path and result is not None:
            self._store_structure_cache(cache_path, result)

        self.last_call_cache_hit = False
        return _stringify_mcp_tool_result(result)

    async def close(self):
        """Корректно закрывает HTTP-клиент."""
        await self.client.aclose()
