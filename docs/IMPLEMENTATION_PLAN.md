# Phased implementation plan

This is the build order used for the repository. The architecture is fixed before implementation so each phase extends the same data model and request paths rather than introducing parallel implementations.

## Phase 0 — Requirements and architecture

**Scope:** Translate the assignment into components and establish the shared data model, voice path and caller-confirmation policy.

**Decisions:**
- Pipecat Python for the voice agent.
- ElevenLabs for realtime speech recognition and speech generation.
- Google Gemini through Pipecat's Google LLM service for reasoning and function calling.
- React + TypeScript + Vite for the dashboard.
- Small WebRTC for browser audio transport; it avoids a third-party room account for a local demo.
- FastAPI plus SQLite for dashboard reads and durable appointment state.

**Exit criteria:** Component diagram, data relationships and tool boundaries are documented before code is written.

## Phase 1 — Appointment domain and persistence

**Scope:** Build doctors, time slots, appointments and a single appointment service.

**Implementation:**
- Create the SQLite schema and indexes.
- Seed four fictional doctors and weekday availability.
- Implement doctor search and slot availability.
- Implement transactional booking and phone-owned cancellation.
- Add a read API for doctors, available slots, overview metrics and appointment history.

**Exit criteria:** Domain tests can create a booking, prevent a second booking of the same slot, cancel the booking with the matching phone number and reject an unrelated phone number.

## Phase 2 — Pipecat voice pipeline

**Scope:** Connect browser audio to STT, LLM and TTS.

**Implementation:**
- Configure Small WebRTC transport.
- Add ElevenLabs realtime STT.
- Add Gemini using `GoogleLLMService`.
- Add ElevenLabs TTS.
- Add Silero VAD to the user context aggregator.
- Create a per-call worker and isolated session state.

**Exit criteria:** A caller can start a browser call, hear the greeting and exchange speech with the agent.

## Phase 3 — Appointment tools and guardrails

**Scope:** Connect Gemini function calling to the appointment domain.

**Implementation:**
- Register availability, booking and cancellation tools in `LLMContext`.
- Add phone capture and explicit phone read-back confirmation tools.
- Require a confirmed number before booking or cancellation.
- Return the exact available slot IDs to the model and validate the selected ID in the domain layer.
- Require an appointment reference when several active appointments exist.

**Exit criteria:** The agent completes an availability-to-booking conversation and a cancellation conversation; server-side validation rejects an unconfirmed number and a slot conflict.

## Phase 4 — Frontend dashboard and call experience

**Scope:** Surface the voice agent and appointment state in one browser application.

**Implementation:**
- Build the overview, doctor cards and appointment table.
- Add a phone-style call modal with connection states, timer, microphone control and end-call action.
- Render caller and assistant transcript events.
- Poll the dashboard read API so bookings/cancellations become visible after tools run.
- Add responsive layouts for narrower screens.

**Exit criteria:** The call can be started and ended from the dashboard; doctors, slots, transcript and appointments are visible.

## Phase 5 — Verification and handoff

**Scope:** Make the repository runnable by another developer.

**Implementation:**
- Add environment examples and `.gitignore`.
- Document architecture, install and run commands, provider keys and demo data.
- Add basic domain tests and Python syntax verification.
- Provide submission pipeline description and a short video checklist.

**Exit criteria:** The project can be installed from the README and the three processes run locally without source edits.
