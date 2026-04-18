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

from ai_client import AIClient
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

ai_client = AIClient()
mcp_1c = MCPClient1C()
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "5"))


def extract_mcp_call(ai_response: str) -> Optional[Tuple[str, dict]]:
    """Ищет MCP_CALL в произвольном тексте и возвращает (tool, arguments)."""

    if not ai_response:
        return None

    marker = "MCP_CALL:"
    marker_index = ai_response.find(marker)
    if marker_index == -1:
        return None

    remainder = ai_response[marker_index + len(marker) :].strip()
    if not remainder:
        return None

    json_start = remainder.find("{")
    if json_start == -1:
        return None

    brace_level = 0
    json_chars = []
    for char in remainder[json_start:]:
        json_chars.append(char)
        if char == "{":
            brace_level += 1
        elif char == "}":
            brace_level -= 1
            if brace_level == 0:
                break

    if brace_level != 0:
        return None

    json_payload = "".join(json_chars)
    try:
        data = json.loads(json_payload)
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
    await ai_client.close()
    await mcp_1c.close()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот-помощник для работы с 1С через MCP.\n\n"
        "📋 **Возможности:**\n"
        "• Отвечаю на вопросы о данных в 1С\n"
        "• Запрашиваю информацию через MCP-инструменты\n"
        "• Автоматически анализирую ошибки и уточняю запросы\n"
        "• Поддерживаю контекст диалога (до 20 сообщений)\n\n"
        "🔧 **Поддерживаемые AI-модели:** DeepSeek, OpenAI, Anthropic, Google Gemini\n\n"
        "💡 **Как использовать:**\n"
        "Просто опиши, что нужно из базы 1С. Например:\n"
        "\"Какие документы продаж были вчера?\"\n"
        "\"Сколько товаров осталось на складе?\"\n"
        "\"Покажи структуру документа РеализацияТоваровУслуг\"\n\n"
        "📝 **Доступные команды:** /help"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📋 **Доступные команды:**\n\n"
        "• /start — приветственное сообщение\n"
        "• /help — эта справка\n"
        "• /clear — очистить историю диалога\n\n"
        "🔧 **Настройки:**\n"
        "Бот поддерживает различные AI-модели через переменные окружения:\n"
        "• AI_MODEL_PROVIDER — провайдер (deepseek, openai, anthropic, google)\n"
        "• AI_MODEL_API_KEY — API-ключ\n"
        "• AI_MODEL_BASE_URL — URL API\n"
        "• AI_MODEL_NAME — имя модели\n\n"
        "⚙️ **MCP-интеграция:**\n"
        "• MCP_SERVER_URL — URL MCP-сервера 1С\n"
        "• MCP_AUTH_USERNAME/PASSWORD — аутентификация (опционально)\n"
        "• MAX_ITERATIONS — лимит итераций для уточнения запросов (по умолчанию 5)"
    )


@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    ContextManager.clear_dialog(message.chat.id)
    await message.answer("✅ История диалога для этого чата очищена.")


@dp.message(F.text)
async def handle_message(message: types.Message):
    chat_id = message.chat.id
    user_text = message.text or ""

    full_context = ContextManager.build_full_context(chat_id, user_text)

    await bot.send_chat_action(chat_id, action="typing")

    try:
        ai_response = await ai_client.get_response(full_context)
    except Exception as exc:
        await message.answer(f"Не удалось получить ответ от ИИ: {exc}")
        return

    mcp_call = extract_mcp_call(ai_response)
    if mcp_call:
        tool_name, tool_arguments = mcp_call
        iteration = 0
        last_error = None
        conversation_history = list(full_context)
        conversation_history.append({"role": "assistant", "content": ai_response})

        while iteration < MAX_ITERATIONS:
            cache_hit = False

            try:
                mcp_result_raw = await mcp_1c.call_tool(tool_name, tool_arguments)
                last_error = None
                cache_hit = bool(getattr(mcp_1c, "last_call_cache_hit", False))
            except Exception as exc:
                last_error = str(exc)
                mcp_result_raw = ""
                cache_hit = False

            if not cache_hit:
                iteration += 1
                await message.answer(
                    f"⏳ Итерация {iteration}/{MAX_ITERATIONS}. Выполняю MCP-инструмент: `{tool_name}`..."
                )
            else:
                await message.answer(
                    f"📄 Использую кэшированную структуру `{tool_name}` без увеличения счётчика попыток."
                )

            iteration_messages = [
                {
                    "role": "user",
                    "content": (
                        "Ниже результат вызова MCP-инструмента."
                        if not last_error
                        else "При вызове MCP-инструмента возникла ошибка."
                    ),
                }
            ]

            if last_error:
                iteration_messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Ошибка вызова инструмента `{tool_name}`: {last_error}."
                            " Если это recoverable ошибка (например, неверные аргументы), предложи скорректировать запрос"
                            " и покажи скорректированный MCP_CALL. Если ошибку исправить нельзя, сообщи, что запрос не"
                            " выполнен."
                        ),
                    }
                )
            else:
                iteration_messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Результат вызова MCP-инструмента `{tool_name}` (сырые данные):\n{mcp_result_raw}\n\n"
                            "Сформулируй понятный ответ пользователю по его последнему сообщению. Если результат неполный"
                            " или требует дополнительного запроса, предложи скорректированный MCP_CALL."
                        ),
                    }
                )

            follow_up = conversation_history + iteration_messages

            await bot.send_chat_action(chat_id, action="typing")
            try:
                ai_response = await ai_client.get_response(follow_up, max_tokens=4000)
            except Exception as exc:
                await message.answer(f"Не удалось обработать результат через ИИ: {exc}")
                return

            conversation_history.extend(iteration_messages)
            conversation_history.append({"role": "assistant", "content": ai_response})

            new_call = extract_mcp_call(ai_response)
            if new_call:
                tool_name, tool_arguments = new_call
                continue

            await message.answer(ai_response)
            ContextManager.update_dialog(chat_id, user_text, ai_response)
            return

        await message.answer(
            "Не удалось получить корректный ответ после нескольких попыток. Попробуйте уточнить запрос."
        )
        ContextManager.update_dialog(chat_id, user_text, ai_response)
        return

    await message.answer(ai_response)
    ContextManager.update_dialog(chat_id, user_text, ai_response)


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
