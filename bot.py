# bot.py
import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from deepseek_client import DeepSeekClient
from context_manager import ContextManager
from mcp_client_1c import MCPClient1C

# Загружаем переменные окружения из .env
load_dotenv()

# Инициализация компонентов
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

deepseek = DeepSeekClient()
mcp_1c = MCPClient1C()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start."""
    await message.answer(
        "Привет! Я бот-помощник с ИИ от DeepSeek.\n"
        "Я помню контекст нашего диалога (последние 20 сообщений).\n"
        "Могу выполнять запросы к базе 1С.\n"
        "Просто напиши, что тебе нужно."
    )

@dp.message()
async def handle_message(message: types.Message):
    """Основной обработчик текстовых сообщений."""
    chat_id = message.chat.id
    user_text = message.text

    # 1. Строим полный контекст: глобальные инструкции + история диалога + текущий запрос
    full_context = ContextManager.build_full_context(chat_id, user_text)

    # 2. Показываем статус "печатает..."
    await bot.send_chat_action(chat_id, action="typing")

    # 3. Получаем первый ответ от DeepSeek (он может содержать команду 1С_QUERY)
    ai_response = await deepseek.get_response(full_context)

    # 4. Проверяем, нужно ли обращаться к 1С
    if ai_response.startswith("1С_QUERY:"):
        query_text = ai_response.replace("1С_QUERY:", "").strip()

        # Информируем пользователя о начале выполнения запроса
        await message.answer(f"⏳ Выполняю запрос к 1С: «{query_text}»...")

        # Отправляем запрос к MCP-серверу 1С
        mcp_result = await mcp_1c.call_tool("query_data", {"query": query_text})

        # Формируем дополнительное системное сообщение с результатом из 1С
        system_info = {
            "role": "system",
            "content": f"Ответ от 1С на запрос пользователя: {mcp_result}"
        }

        # Повторно обращаемся к DeepSeek, чтобы он сформулировал финальный ответ
        final_response = await deepseek.get_response([system_info] + full_context)

        # Отправляем итоговый ответ пользователю
        await message.answer(final_response)

        # Сохраняем диалог (вопрос пользователя и финальный ответ ассистента)
        ContextManager.update_dialog(chat_id, user_text, final_response)
    else:
        # Обычный ответ ИИ (без обращения к 1С)
        await message.answer(ai_response)
        ContextManager.update_dialog(chat_id, user_text, ai_response)

async def main():
    """Запуск бота."""
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    