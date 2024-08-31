from dotenv import load_dotenv
import os

# Подключение API и BD
load_dotenv()

API_KEY = os.getenv("API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if API_KEY is None:
    raise ValueError(
        "Переменная окружения API_KEY не установлена."
    )

if DATABASE_URL is None:
    raise ValueError(
        "Переменная окружения DATABASE_URL не установлена."
    )