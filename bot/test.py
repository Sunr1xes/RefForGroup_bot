import asyncio
import logging 
from database import Base, engine
from sqlalchemy.exc import SQLAlchemyError

async def init_db():
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
            logging.info("Таблицы успешно созданы")
        except SQLAlchemyError as e:
            logging.error(f"Ошибка при создании таблиц: {e}")

if __name__ == "__main__":
    asyncio.run(init_db())
