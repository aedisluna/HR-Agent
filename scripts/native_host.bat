@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."

if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
  "%PROJECT_ROOT%\.venv\Scripts\python.exe" "%~dp0native_host.py" %*
) else (
  rem The project requires Python 3.11+; bare py -3 may select an older default runtime.
  py -3.11 "%~dp0native_host.py" %*
)
