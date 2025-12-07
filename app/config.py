import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


def _get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


@dataclass
class Settings:
    truck_bot_token: str
    elevator_bot_token: str
    elevator_target_id: int | None
    database_url: str
    notification_poll_interval_seconds: int
    default_timezone: str
    slot_duration_minutes: int


def load_settings() -> Settings:
    raw_target = os.getenv("ELEVATOR_TARGET_ID")
    return Settings(
        truck_bot_token=_get_env("TRUCK_BOT_TOKEN", ""),
        elevator_bot_token=_get_env("ELEVATOR_BOT_TOKEN", ""),
        elevator_target_id=int(raw_target) if raw_target else None,
        database_url=_get_env("DATABASE_URL", "sqlite:///queue.db"),
        notification_poll_interval_seconds=int(
            _get_env("NOTIFICATION_POLL_INTERVAL_SECONDS", "30")
        ),
        default_timezone=_get_env("DEFAULT_TIMEZONE", "Europe/Moscow"),
        slot_duration_minutes=int(_get_env("SLOT_DURATION_MINUTES", "60")),
    )


settings = load_settings()
