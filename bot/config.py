from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()

# Переменные окружения
REQUIRED_VARS = ["API_KEY", "DATABASE_URL", "GROUP_CHAT_ID", "ADMIN_MAKSIM", "ADMIN_ROMAN", "ADMIN_ACCOUNT"]
env_vars = {var: os.getenv(var) for var in REQUIRED_VARS}

# Проверка наличия всех необходимых переменных окружения
for var, value in env_vars.items():
    if value is None:
        raise ValueError(f"Переменная окружения {var} не установлена.")

# Присвоение значений переменным
API_KEY = env_vars["API_KEY"]
DATABASE_URL = env_vars["DATABASE_URL"]
GROUP_CHAT_ID = env_vars["GROUP_CHAT_ID"]
ADMIN_MAKSIM = env_vars["ADMIN_MAKSIM"]
ADMIN_ROMAN = env_vars["ADMIN_ROMAN"]
ADMIN_ACCOUNT = env_vars["ADMIN_ACCOUNT"]
REFERRAL_PERCENTAGE = 0.1

STATUS_MAP = {
    'pending': 'В обработке',
    'cancelled': 'Отменено',
    'approved': 'Одобрено'
}
