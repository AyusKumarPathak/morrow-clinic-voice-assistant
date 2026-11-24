from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any

from app.db import CLINIC_TIMEZONE, get_connection, iso_now


def normalize_phone_number(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if not 10 <= len(digits) <= 15:
        raise ValueError("Please use a valid phone number containing 10 to 15 digits.")
    return digits


def format_phone_number(value: str) -> str:
    if len(value) == 10:
        return f"{value[:5]} {value[5:]}"
    return value


def _doctor_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "specialty": row["specialty"],
        "qualifications": row["qualifications"],
        "experience_years": row["experience_years"],
        "location": row["location"],
        "color": row["color"],
    }


def list_doctors() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM doctors ORDER BY name").fetchall()
        return [_doctor_dict(row) for row in rows]


def _appointment_from_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "doctor_id": row["doctor_id"],
        "doctor_name": row["doctor_name"],
        "specialty": row["specialty"],
        "location": row["location"],
        "slot_id": row["slot_id"],
        "starts_at": row["starts_at"],
        "ends_at": row["ends_at"],
        "phone_number": row["phone_number"],
        "status": row["status"],
        "booked_at": row["booked_at"],
        "cancelled_at": row["cancelled_at"],
    }


def list_appointments(status: str | None = "booked") -> list[dict[str, Any]]:
    where = "WHERE a.status = ?" if status in {"booked", "cancelled"} else ""
    params = (status,) if where else ()
    with get_connection() as connection:
        rows = connection.execute(
            f"""SELECT a.*, d.name AS doctor_name, d.specialty, d.location,
                       s.starts_at, s.ends_at
                FROM appointments a
                JOIN doctors d ON d.id = a.doctor_id
                JOIN slots s ON s.id = a.slot_id
                {where}
                ORDER BY s.starts_at ASC""",
            params,
        ).fetchall()
        return [_appointment_from_row(row) for row in rows]


def get_appointment_stats() -> dict[str, int]:
    with get_connection() as connection:
        row = connection.execute(
            """SELECT
                SUM(CASE WHEN status = 'booked' THEN 1 ELSE 0 END) AS booked,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
               FROM appointments"""
        ).fetchone()
        available = connection.execute(
            "SELECT COUNT(*) AS count FROM slots WHERE status = 'available' AND starts_at > ?",
            (iso_now(),),
        ).fetchone()["count"]
    return {
        "booked": int(row["booked"] or 0),
        "cancelled": int(row["cancelled"] or 0),
        "available_slots": int(available),
    }


def find_doctors(query: str = "", specialty: str = "") -> list[dict[str, Any]]:
    query = (query or "").strip().casefold()
    specialty = (specialty or "").strip().casefold()
    doctors = list_doctors()
    matches = [
        doctor
        for doctor in doctors
        if (not query or query in doctor["name"].casefold() or query in doctor["specialty"].casefold())
        and (not specialty or specialty in doctor["specialty"].casefold())
    ]
    return matches


def get_available_slots(
    doctor_name: str = "", specialty: str = "", requested_date: str = ""
) -> list[dict[str, Any]]:
    doctors = find_doctors(doctor_name, specialty)
    if not doctors:
        return []

    doctor_ids = [doctor["id"] for doctor in doctors]
    placeholders = ",".join("?" for _ in doctor_ids)
    sql = f"""SELECT s.id, s.doctor_id, s.starts_at, s.ends_at,
                     d.name AS doctor_name, d.specialty, d.location
              FROM slots s JOIN doctors d ON d.id = s.doctor_id
              WHERE s.status = 'available' AND s.doctor_id IN ({placeholders})
                AND s.starts_at > ?"""
    params: list[str] = [*doctor_ids, iso_now()]
    if requested_date:
        try:
            parsed_date = date.fromisoformat(requested_date.strip())
        except ValueError as exc:
            raise ValueError("Please provide the date in YYYY-MM-DD format.") from exc
        sql += " AND substr(s.starts_at, 1, 10) = ?"
        params.append(parsed_date.isoformat())
    sql += " ORDER BY s.starts_at LIMIT 240"

    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def book_slot(phone_number: str, slot_id: str) -> dict[str, Any]:
    normalized_phone = normalize_phone_number(phone_number)
    if not slot_id.strip():
        raise ValueError("A slot ID is required to book an appointment.")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        slot = connection.execute(
            """SELECT s.*, d.name AS doctor_name, d.specialty, d.location
               FROM slots s JOIN doctors d ON d.id = s.doctor_id
               WHERE s.id = ?""",
            (slot_id,),
        ).fetchone()
        if slot is None:
            raise ValueError("That time slot could not be found. Please check availability again.")
        if slot["status"] != "available":
            raise ValueError("That slot has just been taken. Please choose another available time.")
        if datetime.fromisoformat(slot["starts_at"]) <= datetime.now(CLINIC_TIMEZONE):
            raise ValueError("That appointment time has already passed. Please choose a future slot.")

        appointment_id = f"APT-{uuid.uuid4().hex[:8].upper()}"
        connection.execute(
            """INSERT INTO appointments
               (id, slot_id, doctor_id, phone_number, status, booked_at)
               VALUES (?, ?, ?, ?, 'booked', ?)""",
            (appointment_id, slot_id, slot["doctor_id"], normalized_phone, iso_now()),
        )
        updated = connection.execute(
            "UPDATE slots SET status = 'booked' WHERE id = ? AND status = 'available'",
            (slot_id,),
        ).rowcount
        if updated != 1:
            raise ValueError("That slot is no longer available. Please choose another time.")

        return {
            "id": appointment_id,
            "slot_id": slot_id,
            "doctor_name": slot["doctor_name"],
            "specialty": slot["specialty"],
            "location": slot["location"],
            "starts_at": slot["starts_at"],
            "ends_at": slot["ends_at"],
            "phone_number": normalized_phone,
            "status": "booked",
        }


def get_active_appointments_for_phone(phone_number: str) -> list[dict[str, Any]]:
    normalized_phone = normalize_phone_number(phone_number)
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT a.*, d.name AS doctor_name, d.specialty, d.location,
                      s.starts_at, s.ends_at
               FROM appointments a
               JOIN doctors d ON d.id = a.doctor_id
               JOIN slots s ON s.id = a.slot_id
               WHERE a.phone_number = ? AND a.status = 'booked'
               ORDER BY s.starts_at""",
            (normalized_phone,),
        ).fetchall()
    return [_appointment_from_row(row) for row in rows]


def cancel_patient_appointment(phone_number: str, appointment_id: str = "") -> dict[str, Any]:
    normalized_phone = normalize_phone_number(phone_number)
    active = get_active_appointments_for_phone(normalized_phone)
    if appointment_id.strip():
        selected = next((item for item in active if item["id"] == appointment_id.strip()), None)
        if selected is None:
            with get_connection() as connection:
                other_owner = connection.execute(
                    "SELECT phone_number, status FROM appointments WHERE id = ?",
                    (appointment_id.strip(),),
                ).fetchone()
            if other_owner and other_owner["status"] == "booked":
                raise ValueError("That appointment does not belong to this phone number.")
            raise ValueError("That appointment could not be found or is no longer active.")
    elif not active:
        raise ValueError("I could not find an active appointment for that phone number.")
    elif len(active) == 1:
        selected = active[0]
    else:
        return {"needs_selection": True, "appointments": active}

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        updated = connection.execute(
            """UPDATE appointments SET status = 'cancelled', cancelled_at = ?
               WHERE id = ? AND phone_number = ? AND status = 'booked'""",
            (iso_now(), selected["id"], normalized_phone),
        ).rowcount
        if updated != 1:
            raise ValueError("The appointment could not be cancelled. It may already have changed.")
        connection.execute(
            "UPDATE slots SET status = 'available' WHERE id = ?",
            (selected["slot_id"],),
        )
    selected["status"] = "cancelled"
    return selected
