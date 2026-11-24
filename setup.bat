@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%backend\.venv\Scripts\python.exe"

echo Checking Python 3.11...
py -3.11 --version >nul 2>nul
if errorlevel 1 goto :no_python

if not exist "%PYTHON%" (
  echo Creating backend virtual environment...
  py -3.11 -m venv "%ROOT%backend\.venv"
  if errorlevel 1 goto :failed
)

echo Installing backend dependencies...
"%PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :failed
"%PYTHON%" -m pip install -r "%ROOT%backend\requirements.txt"
if errorlevel 1 goto :failed

if not exist "%ROOT%backend\.env" copy "%ROOT%backend\.env.example" "%ROOT%backend\.env" >nul
if not exist "%ROOT%frontend\.env" copy "%ROOT%frontend\.env.example" "%ROOT%frontend\.env" >nul

echo Checking Node.js version...
node -e "const [a,b]=process.versions.node.split('.').map(Number); process.exit(a>22||(a===22&&b>=14)?0:1)" >nul 2>nul
if errorlevel 1 echo WARNING: @daily-co/daily-js expects Node.js 22.14.0 or newer. Install Node.js 22.14+ to avoid the engine warning.

echo Installing frontend dependencies...
pushd "%ROOT%frontend"
call npm install
if errorlevel 1 goto :frontend_failed
popd

echo.
echo Setup completed successfully.
echo Backend Python: %PYTHON%
echo Next: add GOOGLE_API_KEY and ELEVENLABS_API_KEY to backend\.env
pause
exit /b 0

:no_python
echo ERROR: Python 3.11 was not found by the Windows py launcher.
echo Install Python 3.11 x64, then close and reopen this terminal and run setup.bat again.
echo You can check installed versions with: py -0p
pause
exit /b 1

:frontend_failed
popd
:failed
echo.
echo SETUP FAILED. Read the first error above; setup did not complete.
pause
exit /b 1
