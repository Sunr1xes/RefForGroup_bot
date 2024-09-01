from dotenv import load_dotenv
import os

# Подключение API и BD
load_dotenv()

API_KEY = os.getenv("API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

if API_KEY is None:
    raise ValueError(
        "Переменная окружения API_KEY не установлена."
    )

if DATABASE_URL is None:
    raise ValueError(
        "Переменная окружения DATABASE_URL не установлена."
    )

if GROUP_CHAT_ID is None:
    raise ValueError(
        "Переменная окружения GROUP_CHAT_ID не установлена."
    )