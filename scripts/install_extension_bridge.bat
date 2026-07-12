@echo off
setlocal
set "MANIFEST=%~dp0native_host_manifest.json"

reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.hr_agent.launcher" /ve /t REG_SZ /d "%MANIFEST%" /f
if errorlevel 1 (
  echo Could not install the HR Agent local bridge.
  pause
  exit /b 1
)

echo HR Agent local bridge is installed. Reload the extension in Chrome.
pause
