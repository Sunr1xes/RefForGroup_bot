import aiogram
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ParseMode
import logging 

API_TOKEN = '7175695555:AAEQZofXMkqZyTVdkZdXjENIv_6MGgazL7A'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)