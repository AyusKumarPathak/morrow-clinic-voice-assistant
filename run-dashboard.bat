@echo off
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%frontend\node_modules" (
  echo Frontend dependencies not found. Run setup.bat first.
  pause
  exit /b 1
)
pushd "%ROOT%frontend"
call npm run dev
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
