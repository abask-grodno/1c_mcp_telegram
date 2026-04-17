import os
import re
from pathlib import Path
from typing import List, Dict

# Папки для хранения контекстов
BASE_DIR = Path(__file__).parent
CONTEXTS_DIR = BASE_DIR / "contexts"
DIALOGS_DIR = BASE_DIR / "dialogs"

# Убедимся, что папки существуют
CONTEXTS_DIR.mkdir(exist_ok=True)
DIALOGS_DIR.mkdir(exist_ok=True)

MAX_DIALOG_MESSAGES = 20  # максимум сообщений в истории


class ContextManager:
    """Управление постоянными и пользовательскими контекстами."""

    @staticmethod
    def get_global_context() -> str:
        """Загружает все постоянные файлы .md из папки contexts/ и объединяет их в одну строку."""
        global_parts = []
        for md_file in sorted(CONTEXTS_DIR.glob("*.md")):
            with open(md_file, "r", encoding="utf-8") as f:
                global_parts.append(f.read())
        return "\n\n".join(global_parts)

    @staticmethod
    def get_dialog_messages(chat_id: int) -> List[Dict[str, str]]:
        """
        Загружает историю диалога конкретного пользователя из .md файла.
        Возвращает список сообщений в формате [{"role": "user", "content": "..."}, ...].
        """
        dialog_file = DIALOGS_DIR / f"{chat_id}.md"
        if not dialog_file.exists():
            return []

        messages = []
        with open(dialog_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Разбираем файл по секциям "## user" и "## assistant"
        pattern = r"## (user|assistant)\s*\n(.*?)(?=\n## |\Z)"
        matches = re.findall(pattern, content, re.DOTALL)

        for role, text in matches:
            messages.append({
                "role": role,
                "content": text.strip()
            })

        # Оставляем только последние MAX_DIALOG_MESSAGES сообщений
        return messages[-MAX_DIALOG_MESSAGES:]

    @staticmethod
    def save_dialog_messages(chat_id: int, messages: List[Dict[str, str]]):
        """
        Сохраняет историю диалога в .md файл (только последние MAX_DIALOG_MESSAGES).
        """
        # Берем последние сообщения
        recent = messages[-MAX_DIALOG_MESSAGES:]

        dialog_file = DIALOGS_DIR / f"{chat_id}.md"
        with open(dialog_file, "w", encoding="utf-8") as f:
            f.write(f"# Диалог пользователя {chat_id}\n\n")
            for msg in recent:
                role = msg["role"]
                content = msg["content"]
                f.write(f"## {role}\n{content}\n\n")

    @staticmethod
    def update_dialog(chat_id: int, user_msg: str, assistant_msg: str):
        """
        Добавляет пару сообщений (user, assistant) в историю диалога и обрезает до лимита.
        """
        messages = ContextManager.get_dialog_messages(chat_id)
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})
        ContextManager.save_dialog_messages(chat_id, messages)

    @staticmethod
    def build_full_context(chat_id: int, current_user_msg: str) -> List[Dict[str, str]]:
        """
        Строит полный список сообщений для отправки в DeepSeek:
        - системное сообщение из глобального контекста
        - история диалога (последние сообщения)
        - текущее сообщение пользователя
        """
        global_ctx = ContextManager.get_global_context()
        messages = []

        # Добавляем глобальный контекст как системное сообщение (если не пусто)
        if global_ctx.strip():
            messages.append({"role": "system", "content": global_ctx})

        # Добавляем историю диалога (уже в формате role/content)
        dialog_messages = ContextManager.get_dialog_messages(chat_id)
        messages.extend(dialog_messages)

        # Добавляем текущее сообщение пользователя
        messages.append({"role": "user", "content": current_user_msg})

        return messages
    