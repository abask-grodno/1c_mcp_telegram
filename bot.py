# bot.py
from __future__ import annotations

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command

from deepseek_client import DeepSeekClient
from context_manager import ContextManager
from mcp_client_1c import MCPClient1C

load_dotenv()

LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

handlers = [logging.StreamHandler()]
log_file_path = os.getenv("LOG_FILE")
if log_file_path:
    log_path = Path(log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10 MB
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    handlers.append(
        RotatingFileHandler(
            filename=log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    )

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, handlers=handlers)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

deepseek = DeepSeekClient()
mcp_1c = MCPClient1C()

def extract_mcp_call(ai_response: str) -> Optional[Tuple[str, dict]]:
    """
    Ожидаемый формат ответа модели:
    MCP_CALL: {"tool":"tool_name","arguments":{"key":"value"}}
    """
    cleaned = ai_response.strip()
    if not cleaned.startswith("MCP_CALL:"):
        return None

    raw_payload = cleaned.split(":", 1)[1].strip()
    try:
        data = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None

    tool_name = data.get("tool")
    arguments = data.get("arguments", {})
    if not isinstance(tool_name, str) or not tool_name.strip():
        return None
    if not isinstance(arguments, dict):
        return None
    return tool_name.strip(), arguments


@dp.shutdown()
async def on_shutdown():
    await deepseek.close()
    await mcp_1c.close()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот-помощник на DeepSeek.\n"
        "Помню контекст диалога (до 20 сообщений).\n"
        "Могу запрашивать данные в 1С через MCP — опиши, что нужно из базы.\n\n"
        "Команды: /clear — очистить историю диалога."
    )


@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    ContextManager.clear_dialog(message.chat.id)
    await message.answer("История диалога для этого чата очищена.")


@dp.message(F.text)
async def handle_message(message: types.Message):
    chat_id = message.chat.id
    user_text = message.text or ""

    full_context = ContextManager.build_full_context(chat_id, user_text)

    await bot.send_chat_action(chat_id, action="typing")

    try:
        ai_response = await deepseek.get_response(full_context)
    except Exception as exc:
        await message.answer(f"Не удалось получить ответ от ИИ: {exc}")
        return

    mcp_call = extract_mcp_call(ai_response)
    if mcp_call:
        tool_name, tool_arguments = mcp_call
        await message.answer(f"⏳ Выполняю MCP-инструмент: `{tool_name}`...")

        try:
            mcp_result = await mcp_1c.call_tool(tool_name, tool_arguments)
        except Exception as exc:
            await message.answer(f"Ошибка при обращении к 1С: {exc}")
            return

        follow_up = list(full_context)
        follow_up.append(
            {
                "role": "user",
                "content": (
                    f"Результат вызова MCP-инструмента `{tool_name}` (сырые данные):\n{mcp_result}\n\n"
                    "Сформулируй понятный ответ пользователю по его последнему сообщению. "
                    "Не выдумывай цифры — используй только то, что есть в результате."
                ),
            }
        )

        await bot.send_chat_action(chat_id, action="typing")
        try:
            final_response = await deepseek.get_response(follow_up, max_tokens=4000)
        except Exception as exc:
            await message.answer(f"Не удалось сформировать финальный ответ: {exc}")
            return

        await message.answer(final_response)
        ContextManager.update_dialog(chat_id, user_text, final_response)
    else:
        await message.answer(ai_response)
        ContextManager.update_dialog(chat_id, user_text, ai_response)


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
