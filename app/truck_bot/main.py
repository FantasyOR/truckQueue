import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import settings
from app.db import init_db
from app.truck_bot.handlers import router


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("token:", settings.truck_bot_token)
    bot = Bot(token=settings.truck_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
