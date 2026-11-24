# Morrow Clinic — Voice Appointment Assistant

A browser-based voice assistant for checking doctor availability, booking an appointment, and cancelling an existing appointment. The voice pipeline is built with Pipecat, ElevenLabs speech services and Google Gemini. The React dashboard reads from the same SQLite database used by the voice tools.

The repository is organised as two backend processes and one frontend process:

- **Clinic API (`:8000`)** — FastAPI read API for doctors, slots, appointments and overview data.
- **Pipecat voice runner (`:7860`)** — WebRTC signalling and the live STT → LLM → tools → TTS pipeline.
- **Dashboard (`:5173`)** — React, TypeScript and Vite application with the call screen and live transcript.

SQLite is the shared source of truth. The domain layer and database schema are shared by the API process and the voice runner, so a tool call updates the same records the dashboard polls.

## Assignment coverage

| Assignment requirement | Implementation |
| --- | --- |
| Pipecat voice pipeline | `backend/app/voice/bot.py` |
| ElevenLabs STT | `ElevenLabsRealtimeSTTService` |
| ElevenLabs TTS | `ElevenLabsTTSService` |
| Gemini LLM | `GoogleLLMService` |
| `check_doctor_availability` | Pipecat function tool backed by SQLite |
| `book_appointment` | Pipecat function tool backed by SQLite |
| `cancel_appointment` | Pipecat function tool backed by SQLite |
| Caller identified by spoken phone number | Per-call state; no login, OTP or caller-ID lookup |
| Number read-back before mutation | `capture_phone_number` + `confirm_phone_number`; mutation tools reject unconfirmed sessions |
| Start and end call from browser | Phone-style call modal using Pipecat Small WebRTC client |
| Live conversation transcript | Pipecat user-input and bot-output events in the call modal |
| Doctors and available slots | Dashboard doctor cards and availability API |
| Appointments update after mutations | Dashboard refreshes its read API every four seconds |
| VAD bonus | Silero VAD in the Pipecat user context aggregator |
| Phone-style screen bonus | Connecting/connected/error states, timer, mute, end-call and transcript |

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the component diagram, request paths, data model and identity rules. See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the phased build plan, and [docs/PIPELINE_DESCRIPTION.md](docs/PIPELINE_DESCRIPTION.md) for a short explanation suitable for the submission form.

## Requirements

- Python **3.11 or 3.12** (the backend project targets `>=3.11,<3.13`)
- Node.js **22.14.0 or newer** and npm (the Daily WebRTC client dependency declares this minimum)
- A Google AI Studio API key
- An ElevenLabs API key with speech-to-text and text-to-speech access
- A modern browser with microphone permissions enabled

The app uses ElevenLabs and Gemini only for the live voice experience. The dashboard API and mock appointment data work locally without external API keys.

## Setup

### 1. Backend environment

**Windows quick setup:** install Python 3.11 x64 and Node.js 22.14.0 or newer. From the repository root, run:

```powershell
.\setup.bat
```

The script creates `backend\.venv`, installs the backend dependencies and frontend packages, and stops if a step fails. It uses Python 3.11 explicitly; it will not silently fall back to a different global Python version. Then add your provider keys to `backend\.env`.

To start the services, open three terminals in the repository root and run `run-api.bat`, `run-voice.bat` and `run-dashboard.bat` respectively.

**Manual setup (Windows, macOS or Linux):** from the repository root:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Install the project:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create the backend environment file:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Set the following values in `backend/.env`:

```env
GOOGLE_API_KEY=your_google_ai_studio_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
GEMINI_MODEL=gemini-3.5-flash-lite
```

Use a voice ID available in your ElevenLabs account if the example voice is not available to you. Do not put credentials in frontend environment files or commit `.env`.

### 2. Start the Clinic API

Open a terminal at `backend/`, activate the virtual environment and run:

```bash
python run_api.py
```

The API starts at `http://localhost:8000`. The first startup creates `backend/data/appointments.db` and seeds the demo doctors and time slots.

Useful endpoints:

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/api/overview`
- `GET http://localhost:8000/api/doctors`
- `GET http://localhost:8000/api/availability`
- `GET http://localhost:8000/api/appointments?status=booked`
- `GET http://localhost:8000/api/appointments?status=cancelled`

### 3. Start the Pipecat voice runner

Open a second terminal at `backend/`, activate the same virtual environment and run:

```bash
python -m app.voice.bot -t webrtc --host 0.0.0.0 --port 7860
```

The Pipecat runner starts a WebRTC session endpoint at `http://localhost:7860/start`. The browser uses this endpoint to start the bot and establish the WebRTC connection. The runner also provides the `/status` endpoint.

### 4. Start the React dashboard

Open a third terminal at `frontend/`:

```bash
npm install
```

Copy the frontend environment file:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Then run:

```bash
npm run dev
```

Open `http://localhost:5173` in Chrome or Edge. Use **Try a call**, allow microphone access and speak to the assistant.

## Demo data

The first database initialisation creates four fictional doctors and the next ten days of weekday slots. It also creates two fictional appointments for the test phone number `9000000001` so that the appointment list is not empty on first launch.

For a booking demo, say a phone number, confirm the number when the assistant reads it back, ask for a doctor or specialty, select one of the offered times and confirm the booking. For a cancellation demo, use `9000000001` and confirm the read-back. The assistant will list the matching appointments and ask which one to cancel if more than one is found.

All doctor, patient and appointment records are synthetic demo data. Do not use this project to store real patient information.

## How identity and confirmation work

The voice runner creates a separate identity state for each call. The caller's spoken number is normalised and stored as a pending value. The assistant reads the number back and asks the caller to confirm it. Only after an affirmative response does it call `confirm_phone_number`. Both mutation tools check the session's verified number before accessing the appointment service. The number is not inferred from the browser, request headers, session ID or caller ID.

This is an assignment-level confirmation guard, not a production authentication system. A deployed healthcare system would need proper identity verification, access controls, audit logs, encryption, retention policies and compliance review.

## Data and concurrency

SQLite uses foreign keys, WAL mode, a busy timeout and explicit write transactions for appointment mutations. Booking locks the write transaction, checks the slot status and marks it booked before the transaction commits. This prevents two callers from booking the same slot in a normal single-host deployment. Cancellation checks that the active appointment belongs to the verified phone number and restores the slot only after a successful cancellation.

## Useful development commands

```bash
# Backend syntax check
cd backend
python -m compileall app run_api.py

# Run domain tests (install pytest first)
python -m pip install pytest
pytest -q

# Frontend production build
cd ../frontend
npm run build
```

## Troubleshooting

**The call screen opens but the assistant does not connect**

Check that the Pipecat runner is running on port 7860 and its `/status` endpoint responds. Confirm both API keys are set in `backend/.env`. Check the backend terminal for the first provider error.

**The browser does not capture audio**

Allow microphone access for `localhost`. WebRTC microphone access requires a secure context; localhost is treated as secure by modern browsers. Close other applications that may be holding the microphone and reload the page.

**Gemini or ElevenLabs returns an authentication or quota error**

Confirm the key is active and has access to the selected model/voice and required API features. The dashboard data API can still be used while the voice provider is unavailable.

**No slots are listed**

The seed data creates upcoming weekday slots. It skips Sundays and slots less than 30 minutes ahead. Restarting the services does not reset an existing database. To reseed a clean demo database, stop both backend processes and delete `backend/data/appointments.db`; it will be recreated at next startup.

## Submission checklist

- [ ] Add valid Google and ElevenLabs keys to `backend/.env`.
- [ ] Start the API, Pipecat runner and Vite dashboard.
- [ ] Complete one booking flow from the browser call screen.
- [ ] Confirm the new appointment appears in the dashboard.
- [ ] Record a short video (up to three minutes) showing the spoken phone number, read-back confirmation, availability check and successful booking.
- [ ] Submit the repository link, video and [pipeline description](docs/PIPELINE_DESCRIPTION.md) in the assignment form.

## License

This project was prepared as an internship assignment demo. Review provider SDK licences and terms before redistribution or production use.
