import csv
import io
from typing import Iterable

from app.models import Booking


def bookings_to_csv(bookings: Iterable[Booking]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["license_plate", "slot_start", "slot_end", "is_late", "unloaded"])
    for booking in bookings:
        is_late = booking.arrived_at is not None and booking.arrived_at > booking.slot_start
        unloaded = booking.unloaded_at is not None
        writer.writerow(
            [
                booking.license_plate,
                booking.slot_start.isoformat(),
                booking.slot_end.isoformat(),
                str(is_late),
                str(unloaded),
            ]
        )
    return output.getvalue().encode("utf-8")
