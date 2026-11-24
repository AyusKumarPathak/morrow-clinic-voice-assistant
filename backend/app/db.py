from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

from app.config import database_path

CLINIC_TIMEZONE = ZoneInfo("Asia/Kolkata")

DOCTORS = [
    {
        "id": "doc-ananya-rao",
        "name": "Dr. Ananya Rao",
        "specialty": "Cardiology",
        "qualifications": "MBBS, MD, DM Cardiology",
        "experience_years": 12,
        "location": "Indiranagar Clinic",
        "color": "sage",
    },
    {
        "id": "doc-rohan-mehta",
        "name": "Dr. Rohan Mehta",
        "specialty": "Dermatology",
        "qualifications": "MBBS, MD Dermatology",
        "experience_years": 9,
        "location": "Indiranagar Clinic",
        "color": "blue",
    },
    {
        "id": "doc-priya-nair",
        "name": "Dr. Priya Nair",
        "specialty": "General Medicine",
        "qualifications": "MBBS, MD Internal Medicine",
        "experience_years": 15,
        "location": "Koramangala Clinic",
        "color": "rose",
    },
    {
        "id": "doc-amit-kulkarni",
        "name": "Dr. Amit Kulkarni",
        "specialty": "Orthopedics",
        "qualifications": "MBBS, MS Orthopedics",
        "experience_years": 11,
        "location": "Koramangala Clinic",
        "color": "amber",
    },
]


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path(), timeout=15, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS doctors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                specialty TEXT NOT NULL,
                qualifications TEXT NOT NULL,
                experience_years INTEGER NOT NULL,
                location TEXT NOT NULL,
                color TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS slots (
                id TEXT PRIMARY KEY,
                doctor_id TEXT NOT NULL REFERENCES doctors(id),
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'available'
                    CHECK (status IN ('available', 'booked')),
                UNIQUE(doctor_id, starts_at)
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id TEXT PRIMARY KEY,
                slot_id TEXT NOT NULL REFERENCES slots(id),
                doctor_id TEXT NOT NULL REFERENCES doctors(id),
                phone_number TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'booked'
                    CHECK (status IN ('booked', 'cancelled')),
                booked_at TEXT NOT NULL,
                cancelled_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_slots_doctor_start
                ON slots(doctor_id, starts_at, status);
            CREATE INDEX IF NOT EXISTS idx_appointments_phone_status
                ON appointments(phone_number, status, booked_at);
            """
        )

        for doctor in DOCTORS:
            connection.execute(
                """INSERT OR IGNORE INTO doctors
                   (id, name, specialty, qualifications, experience_years, location, color)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    doctor["id"],
                    doctor["name"],
                    doctor["specialty"],
                    doctor["qualifications"],
                    doctor["experience_years"],
                    doctor["location"],
                    doctor["color"],
                ),
            )

        now = datetime.now(CLINIC_TIMEZONE)
        today = now.date()
        slot_times = [time(9, 30), time(10, 30), time(11, 30), time(14, 0), time(15, 0), time(16, 0)]
        for day_offset in range(0, 10):
            current_day = today + timedelta(days=day_offset)
            if current_day.weekday() == 6:
                continue
            for doctor in DOCTORS:
                for slot_time in slot_times:
                    starts_at = datetime.combine(current_day, slot_time, tzinfo=CLINIC_TIMEZONE)
                    if starts_at <= now + timedelta(minutes=30):
                        continue
                    ends_at = starts_at + timedelta(minutes=30)
                    slot_id = f"{doctor['id']}|{starts_at.strftime('%Y%m%d%H%M')}"
                    connection.execute(
                        """INSERT OR IGNORE INTO slots (id, doctor_id, starts_at, ends_at)
                           VALUES (?, ?, ?, ?)""",
                        (
                            slot_id,
                            doctor["id"],
                            starts_at.isoformat(),
                            ends_at.isoformat(),
                        ),
                    )

        # A small set of clearly fictional records makes the dashboard useful on first run.
        # These numbers are test data and are not associated with real patients.
        seeded = connection.execute("SELECT COUNT(*) AS count FROM appointments").fetchone()["count"]
        if seeded == 0:
            demo_phone = "9000000001"
            available = connection.execute(
                """SELECT s.id, s.doctor_id FROM slots s
                   WHERE s.status = 'available' ORDER BY s.starts_at LIMIT 2"""
            ).fetchall()
            for index, slot in enumerate(available, start=1):
                appointment_id = f"APT-DEMO-00{index}"
                connection.execute(
                    """INSERT INTO appointments
                       (id, slot_id, doctor_id, phone_number, status, booked_at)
                       VALUES (?, ?, ?, ?, 'booked', ?)""",
                    (
                        appointment_id,
                        slot["id"],
                        slot["doctor_id"],
                        demo_phone,
                        now.isoformat(),
                    ),
                )
                connection.execute(
                    "UPDATE slots SET status = 'booked' WHERE id = ?",
                    (slot["id"],),
                )


def local_now() -> datetime:
    return datetime.now(CLINIC_TIMEZONE)


def iso_now() -> str:
    return local_now().isoformat()


def format_datetime(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CLINIC_TIMEZONE)
    return parsed.astimezone(CLINIC_TIMEZONE).isoformat()
