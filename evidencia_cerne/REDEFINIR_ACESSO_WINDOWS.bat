@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente nao configurado. Execute INICIAR_WINDOWS.bat primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import dotenv" >nul 2>nul
if errorlevel 1 (
  echo Instalando dependencia de configuracao...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (echo Falha na instalacao. & pause & exit /b 1)
)
".venv\Scripts\python.exe" redefinir_acesso.py
pause
