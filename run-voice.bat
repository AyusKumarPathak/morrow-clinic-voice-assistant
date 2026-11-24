@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Backend virtual environment not found. Run setup.bat first.
  pause
  exit /b 1
)
pushd "%ROOT%backend"
"%PYTHON%" -m app.voice.bot -t webrtc --host 0.0.0.0 --port 7860
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
