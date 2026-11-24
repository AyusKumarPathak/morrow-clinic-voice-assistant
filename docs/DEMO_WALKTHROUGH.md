# Three-minute demo walkthrough

The assignment asks for a short recording of one complete booking flow. Keep the browser dashboard visible so the reviewer can see the call and the appointment row update.

## Before recording

1. Add valid `GOOGLE_API_KEY` and `ELEVENLABS_API_KEY` values to `backend/.env`.
2. Start the Clinic API, Pipecat voice runner and Vite dashboard in separate terminals.
3. Open `http://localhost:5173`, check that the dashboard API shows as online, and allow microphone access.
4. Start the recording before clicking **Try a call**.

## Suggested recording sequence

| Approx. time | What to show |
| --- | --- |
| 0:00–0:20 | Show the clinic dashboard, doctors, next available slots and the appointment list. Briefly state that the voice service uses Pipecat, ElevenLabs and Gemini. |
| 0:20–0:45 | Click **Try a call**. Show the phone-style call screen and the live transcript. Let the assistant greet you. |
| 0:45–1:15 | Say: “I would like to book an appointment with a dermatologist.” When asked, speak the demo phone number `9000000001`. |
| 1:15–1:35 | Let the assistant read the number back. Clearly say: “Yes, that is correct.” Show the confirmation in the transcript. |
| 1:35–2:15 | Ask for the next available appointment. Select one of the offered slots and confirm that you want to book it. |
| 2:15–2:40 | Show the assistant repeating the doctor, date and time. Close the call and show the new appointment row in the dashboard. |
| 2:40–3:00 | Briefly point out the shared SQLite state and the three appointment tools. End the recording. |

Do not skip the number read-back. It is an explicit assignment rule, and the booking tool refuses to mutate appointment data until the caller confirms it. Do not claim that the call or booking succeeded unless the assistant reports success and the appointment row appears.

## If the recording is focused on cancellation instead

Use the demo number `9000000001`, let the assistant read it back, confirm it, then ask to cancel one of the listed appointments. If more than one appointment is active, choose the appointment by doctor and time after the assistant lists the options. The cancelled appointment should move to the **Cancelled** tab and its time slot should become available again.
