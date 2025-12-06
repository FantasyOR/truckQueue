import asyncio
import logging

from aiogram import Bot

from app.config import settings
from app.db import SessionLocal, init_db
from app.notification_service.logic import process_notifications


async def worker() -> None:
    logging.basicConfig(level=logging.INFO)
    init_db()
    bot = Bot(token=settings.truck_bot_token)
    while True:
        try:
            with SessionLocal() as session:
                await process_notifications(session, bot)
        except Exception as exc:  # pragma: no cover - runtime logging
            logging.exception("Notification loop error: %s", exc)
        await asyncio.sleep(settings.notification_poll_interval_seconds)


def main() -> None:
    asyncio.run(worker())


if __name__ == "__main__":
    main()
