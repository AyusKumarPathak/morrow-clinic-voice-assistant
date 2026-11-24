# Pipeline description

The browser connects to the Python Pipecat runner over Small WebRTC. Incoming audio is transcribed by ElevenLabs realtime STT and passed into a Gemini model through Pipecat's LLM context aggregator. Gemini can call the appointment tools registered in that context. Those tools use a shared Python appointment service backed by SQLite, which is also read by the dashboard API. The assistant's response is converted to speech by ElevenLabs TTS and streamed back to the browser.

The caller's phone number is collected from speech, read back and explicitly confirmed before booking or cancellation. The confirmed number lives only in the current call's state. Silero VAD is used by the context aggregator for speech-turn detection.
