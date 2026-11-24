from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.db import get_connection, init_db
from app.services.appointments import (
    book_slot,
    cancel_patient_appointment,
    get_active_appointments_for_phone,
    get_available_slots,
    normalize_phone_number,
)


def setup_database(tmp_path: Path) -> None:
    os.environ["DATABASE_PATH"] = str(tmp_path / "test_appointments.db")
    init_db()


def test_phone_normalization() -> None:
    assert normalize_phone_number("+91 98765 43210") == "9876543210"
    with pytest.raises(ValueError):
        normalize_phone_number("1234")


def test_book_and_cancel_slot(tmp_path: Path) -> None:
    setup_database(tmp_path)
    slots = get_available_slots(doctor_name="Dr. Ananya Rao")
    assert slots
    selected = slots[0]

    booked = book_slot("9876543210", selected["id"])
    assert booked["status"] == "booked"
    assert booked["phone_number"] == "9876543210"
    assert len(get_active_appointments_for_phone("9876543210")) == 1

    with pytest.raises(ValueError, match="taken"):
        book_slot("9876543210", selected["id"])

    cancelled = cancel_patient_appointment("9876543210", booked["id"])
    assert cancelled["status"] == "cancelled"
    assert get_active_appointments_for_phone("9876543210") == []


def test_cancellation_rejects_wrong_phone(tmp_path: Path) -> None:
    setup_database(tmp_path)
    selected = get_available_slots(doctor_name="Dr. Rohan Mehta")[0]
    booked = book_slot("9876543210", selected["id"])

    with pytest.raises(ValueError, match="does not belong"):
        cancel_patient_appointment("9876543211", booked["id"])


def test_availability_covers_all_doctors_and_excludes_past_slots(tmp_path: Path) -> None:
    setup_database(tmp_path)
    slots = get_available_slots()
    assert {slot["doctor_id"] for slot in slots} == {
        "doc-ananya-rao",
        "doc-rohan-mehta",
        "doc-priya-nair",
        "doc-amit-kulkarni",
    }

    expired_slot_id = slots[0]["id"]
    with get_connection() as connection:
        connection.execute(
            "UPDATE slots SET starts_at = ?, ends_at = ? WHERE id = ?",
            ("2000-01-01T09:00:00+05:30", "2000-01-01T09:30:00+05:30", expired_slot_id),
        )
    assert expired_slot_id not in {slot["id"] for slot in get_available_slots()}


def test_cannot_book_a_past_slot(tmp_path: Path) -> None:
    setup_database(tmp_path)
    selected = get_available_slots(doctor_name="Dr. Ananya Rao")[0]
    with get_connection() as connection:
        connection.execute(
            "UPDATE slots SET starts_at = ?, ends_at = ? WHERE id = ?",
            ("2000-01-01T09:00:00+05:30", "2000-01-01T09:30:00+05:30", selected["id"]),
        )

    with pytest.raises(ValueError, match="already passed"):
        book_slot("9876543210", selected["id"])
