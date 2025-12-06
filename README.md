## Truck Queue MVP

Асинхронный сервис для управления очередью грузовиков на элеватор: два Telegram-бота (водитель и диспетчер), сервис уведомлений и SQLite-база с SQLAlchemy.

### Структура
- `app/config.py` — конфиг из `.env`.
- `app/db.py` — подключение к БД, сессии, инициализация.
- `app/models.py` — ORM-модели.
- `app/utils/` — работа со временем и экспорт в CSV.
- `app/truck_bot/` — бот водителя с FSM бронирования.
- `app/elevator_bot/` — бот диспетчера (расписание, экспорт, действия).
- `app/notification_service/` — циклические уведомления.

### Запуск
1. Создать `.env` по образцу `.env.example`.
2. Установить зависимости: `pip install -r requirements.txt`.
3. Инициализировать БД: `python -m app.db`.
4. Запустить ботов и сервис уведомлений в отдельных процессах:
   - `python -m app.truck_bot.main`
   - `python -m app.elevator_bot.main`
   - `python -m app.notification_service.main`

### Подготовка данных
Создайте хотя бы один элеватор (рабочий день 09:00-17:00, по умолчанию 5 бронируемых слотов):
```python
from datetime import time
from app.db import SessionLocal, init_db
from app.models import Elevator

init_db()
with SessionLocal() as session:
    elevator = Elevator(name="Главный", work_day_start=time(9), work_day_end=time(17))
    session.add(elevator)
    session.commit()
```

### База данных
SQLite-файл, путь задается `DATABASE_URL` (`sqlite:///queue.db` по умолчанию). Миграции не используются — таблицы создаются автоматически.

### Часовой пояс
Все вычисления выполняются в `DEFAULT_TIMEZONE` (по умолчанию `Europe/Moscow`). Даты/время сохраняются timezone-aware.
