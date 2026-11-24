from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_ORIGIN
from app.db import init_db, local_now
from app.services.appointments import (
    get_appointment_stats,
    get_available_slots,
    list_appointments,
    list_doctors,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Clinic Voice Assistant API",
    version="1.0.0",
    description="Read API for the clinic dashboard; appointment mutations happen through the Pipecat tools.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "clinic-api"}


@app.get("/api/overview")
def overview() -> dict:
    stats = get_appointment_stats()
    appointments = list_appointments("booked")
    return {
        "stats": stats,
        "upcoming_appointments": appointments[:5],
        "today": local_now().date().isoformat(),
        "timezone": "Asia/Kolkata",
    }


@app.get("/api/doctors")
def doctors() -> dict:
    items = list_doctors()
    return {"items": items, "count": len(items)}


@app.get("/api/availability")
def availability(
    doctor: str = Query(default="", max_length=100),
    specialty: str = Query(default="", max_length=100),
    date: str = Query(default="", max_length=10),
) -> dict:
    try:
        items = get_available_slots(doctor, specialty, date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": items, "count": len(items)}


@app.get("/api/appointments")
def appointments(status: str = Query(default="booked", pattern="^(booked|cancelled|all)$")) -> dict:
    selected_status = None if status == "all" else status
    items = list_appointments(selected_status)
    return {"items": items, "count": len(items)}
