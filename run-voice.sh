#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/backend"
source .venv/bin/activate
python -m app.voice.bot -t webrtc --host 0.0.0.0 --port 7860
