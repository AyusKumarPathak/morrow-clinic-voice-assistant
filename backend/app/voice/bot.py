from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from loguru import logger

from app.config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_VOICE_ID,
    GEMINI_MODEL,
    GOOGLE_API_KEY,
)
from app.db import CLINIC_TIMEZONE, init_db
from app.services.appointments import (
    book_slot,
    cancel_patient_appointment,
    find_doctors,
    format_phone_number,
    get_available_slots,
    normalize_phone_number,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.elevenlabs.stt import ElevenLabsRealtimeSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

SYSTEM_PROMPT = """You are the appointment desk assistant for Morrow Clinic. You speak with callers using voice.

Your job is to help callers check doctor availability, book one available slot, or cancel one of their
appointments. Keep replies natural, calm, short and easy to understand. Use plain spoken English.
Do not use markdown, lists, emojis, or say internal tool names aloud.

IDENTITY AND CONFIRMATION RULES
- The caller is identified only by the phone number they speak during this call. Never use caller ID,
  login details, an account, a name, or any information from the dashboard as identity.
- Before booking or cancelling, ask the caller to say their phone number.
- Call capture_phone_number with the number they gave you. Read the formatted number returned by the
  tool back to them, digit by digit or in natural groups, and ask whether it is correct.
- Do not book or cancel until the caller clearly confirms that exact number. If they correct it, capture
  the new number and read it back again. A simple affirmative such as yes, correct, that's right, or
  absolutely is required. If the caller says no or is unclear, do not proceed.
- Only after the caller has confirmed the read-back, call confirm_phone_number and pass the caller's
  actual affirmative words in caller_response. Never invent an affirmative response.
- If the confirmation tool reports that the number is not confirmed, do not proceed with a mutation.
- A confirmed number is valid only for this call. Do not disclose appointment details before it is
  confirmed. Do not repeat the full phone number after verification unless needed.

BOOKING FLOW
- First identify the doctor or specialty and the preferred date. If the caller has not specified a date,
  ask whether they have a preference; otherwise check the next available dates.
- Use check_doctor_availability. Read the returned choices clearly and let the caller select one.
- Use the exact slot_id returned by the availability tool. Never invent a slot or claim a booking is
  complete before book_appointment succeeds.
- Before booking, make sure the phone number is confirmed. If the caller has not confirmed it yet, do
  the identity flow first.
- After a successful booking, repeat the doctor, date and time and the appointment reference.

CANCELLATION FLOW
- Confirm the caller's spoken phone number before looking up or cancelling an appointment.
- Use cancel_appointment only after phone confirmation. If more than one appointment is found, explain
  the options and ask which one they mean. Pass the exact appointment_id returned by the tool.
- Never cancel an appointment that is not associated with the confirmed phone number.
- Confirm cancellation only when the tool reports success.

GENERAL RULES
- You are an appointment assistant, not a doctor. Do not diagnose, recommend medication, or provide
  medical advice. For urgent symptoms, tell the caller to contact local emergency services or a clinician.
- If a doctor or specialty is unclear, ask a short follow-up question.
- When a tool returns an error, explain it plainly and offer the next useful step.
- The clinic timezone is Asia/Kolkata. Today's date is provided in the conversation context.
"""


def _affirmative_response(value: str) -> bool:
    text = (value or "").strip().casefold()
    if not text:
        return False
    negative = re.search(r"\b(no|nope|not|incorrect|wrong|don't|do not|stop)\b", text)
    positive = re.search(
        r"\b(yes|yeah|yep|correct|right|that's right|that is right|that's correct|that is correct|absolutely|confirmed|sure)\b",
        text,
    )
    return bool(positive and not negative)


def _safe_result(error: Exception) -> dict[str, Any]:
    return {"ok": False, "message": str(error)}


async def bot(runner_args: RunnerArguments) -> None:
    """Pipecat runner entry point. Each call gets isolated identity state."""
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is missing. Copy .env.example to .env and add your key.")
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is missing. Copy .env.example to .env and add your key.")

    init_db()
    session_state: dict[str, str | None] = {
        "pending_phone": None,
        "verified_phone": None,
    }

    async def capture_phone_number(
        params: FunctionCallParams,
        phone_number: str,
    ) -> None:
        """Store the caller's spoken phone number for read-back.

        Args:
            phone_number: The phone number the caller just said aloud.
        """
        try:
            normalized = normalize_phone_number(phone_number)
        except ValueError as exc:
            session_state["pending_phone"] = None
            session_state["verified_phone"] = None
            await params.result_callback(_safe_result(exc))
            return

        session_state["pending_phone"] = normalized
        session_state["verified_phone"] = None
        await params.result_callback(
            {
                "ok": True,
                "status": "pending_confirmation",
                "formatted_phone_number": format_phone_number(normalized),
                "instruction": "Read this number back to the caller and ask whether it is correct.",
            }
        )

    async def confirm_phone_number(
        params: FunctionCallParams,
        caller_response: str,
    ) -> None:
        """Confirm the phone number after the caller explicitly approves the read-back.

        Args:
            caller_response: The caller's actual words immediately after the number read-back.
        """
        pending = session_state.get("pending_phone")
        if not pending:
            await params.result_callback(
                {"ok": False, "message": "No phone number is waiting for confirmation. Ask the caller for it again."}
            )
            return
        if not _affirmative_response(caller_response):
            session_state["verified_phone"] = None
            await params.result_callback(
                {"ok": False, "status": "not_confirmed", "message": "The caller has not clearly confirmed the number."}
            )
            return

        session_state["verified_phone"] = pending
        await params.result_callback(
            {
                "ok": True,
                "status": "confirmed",
                "message": "The phone number is confirmed for this call.",
            }
        )

    async def check_doctor_availability(
        params: FunctionCallParams,
        doctor_name: str,
        specialty: str,
        date: str,
    ) -> None:
        """Find available appointment slots for a doctor or specialty.

        Args:
            doctor_name: Doctor's name or a search phrase. Use an empty string if unknown.
            specialty: Specialty such as Cardiology, Dermatology, General Medicine, or Orthopedics.
            date: Requested date in YYYY-MM-DD format, or an empty string for the next available slots.
        """
        try:
            doctors = find_doctors(doctor_name, specialty)
            if not doctors:
                await params.result_callback(
                    {
                        "ok": False,
                        "message": "No matching doctor was found.",
                        "available_doctors": [
                            {"name": doctor["name"], "specialty": doctor["specialty"]}
                            for doctor in find_doctors()
                        ],
                    }
                )
                return
            slots = get_available_slots(doctor_name, specialty, date)
            await params.result_callback(
                {
                    "ok": True,
                    "doctors": [
                        {"name": doctor["name"], "specialty": doctor["specialty"], "location": doctor["location"]}
                        for doctor in doctors
                    ],
                    "date_filter": date or "next available",
                    "slots": slots[:18],
                    "message": "No open slots match that date." if not slots else "Slots are available for selection.",
                }
            )
        except Exception as exc:
            logger.exception("Availability tool failed")
            await params.result_callback(_safe_result(exc))

    async def book_appointment(
        params: FunctionCallParams,
        slot_id: str,
    ) -> None:
        """Book an available slot for the caller's confirmed phone number.

        Args:
            slot_id: The exact slot_id returned by check_doctor_availability.
        """
        verified_phone = session_state.get("verified_phone")
        if not verified_phone:
            await params.result_callback(
                {"ok": False, "message": "Phone number is not confirmed. Ask for it and complete the read-back first."}
            )
            return
        try:
            appointment = book_slot(verified_phone, slot_id)
            await params.result_callback({"ok": True, "appointment": appointment})
        except Exception as exc:
            logger.exception("Booking tool failed")
            await params.result_callback(_safe_result(exc))

    async def cancel_appointment(
        params: FunctionCallParams,
        appointment_id: str,
    ) -> None:
        """Cancel an appointment that belongs to the caller's confirmed phone number.

        Args:
            appointment_id: Exact appointment ID returned by this tool. Use an empty string if the caller has not selected one yet.
        """
        verified_phone = session_state.get("verified_phone")
        if not verified_phone:
            await params.result_callback(
                {"ok": False, "message": "Phone number is not confirmed. Ask for it and complete the read-back first."}
            )
            return
        try:
            result = cancel_patient_appointment(verified_phone, appointment_id)
            if result.get("needs_selection"):
                await params.result_callback(
                    {
                        "ok": True,
                        "needs_selection": True,
                        "appointments": result["appointments"],
                        "message": "More than one active appointment was found. Ask which one the caller wants to cancel.",
                    }
                )
                return
            await params.result_callback({"ok": True, "cancelled_appointment": result})
        except Exception as exc:
            logger.exception("Cancellation tool failed")
            await params.result_callback(_safe_result(exc))

    transport_params = {
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    }
    transport: BaseTransport = await create_transport(runner_args, transport_params)

    stt = ElevenLabsRealtimeSTTService(api_key=ELEVENLABS_API_KEY)
    tts = ElevenLabsTTSService(
        api_key=ELEVENLABS_API_KEY,
        settings=ElevenLabsTTSService.Settings(voice=ELEVENLABS_VOICE_ID),
    )
    llm = GoogleLLMService(
        api_key=GOOGLE_API_KEY,
        settings=GoogleLLMService.Settings(
            model=GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    context = LLMContext(
        tools=[
            capture_phone_number,
            confirm_phone_number,
            check_doctor_availability,
            book_appointment,
            cancel_appointment,
        ]
    )
    today = datetime.now(CLINIC_TIMEZONE).date().isoformat()
    context.add_message(
        {
            "role": "developer",
            "content": (
                f"Today's date is {today}. This caller session has its own identity state. "
                "Introduce yourself as the Morrow Clinic appointment assistant, then ask how you can help."
            ),
        }
    )

    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=300,
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport: BaseTransport, client: Any) -> None:
        logger.info("Voice client connected: {}", client)
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport: BaseTransport, client: Any) -> None:
        logger.info("Voice client disconnected: {}", client)
        session_state["pending_phone"] = None
        session_state["verified_phone"] = None
        await runner.cancel()

    await runner.run()


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
