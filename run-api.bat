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
"%PYTHON%" run_api.py
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
