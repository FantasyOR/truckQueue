from __future__ import annotations

from datetime import datetime, time, date
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class BookingStatus:
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    ARRIVED = "ARRIVED"
    UNLOADED = "UNLOADED"
    CANCELLED = "CANCELLED"

    ALL = {PENDING, CONFIRMED, ARRIVED, UNLOADED, CANCELLED}


class Elevator(Base):
    __tablename__ = "elevators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    work_day_start: Mapped[time] = mapped_column(Time(timezone=True), nullable=False)
    work_day_end: Mapped[time] = mapped_column(Time(timezone=True), nullable=False)
    bookable_slots_per_day: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="elevator", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Elevator(id={self.id}, name={self.name})"


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="driver", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Driver(id={self.id}, telegram_user_id={self.telegram_user_id})"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    elevator_id: Mapped[int] = mapped_column(ForeignKey("elevators.id"), nullable=False)
    license_plate: Mapped[str] = mapped_column(String(32), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    queue_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=BookingStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    unloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    last_notified_queue_index: Mapped[Optional[int]] = mapped_column(Integer)

    driver: Mapped["Driver"] = relationship("Driver", back_populates="bookings")
    elevator: Mapped["Elevator"] = relationship("Elevator", back_populates="bookings")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="booking", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Booking(id={self.id}, queue_index={self.queue_index}, status={self.status})"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="notifications")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Notification(id={self.id}, type={self.notification_type})"
