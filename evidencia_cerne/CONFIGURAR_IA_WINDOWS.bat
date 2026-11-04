@echo off
setlocal
cd /d "%~dp0"
title Evidencia+ - Configurar IA
if not exist ".venv\Scripts\python.exe" (
  echo Primeiro execute INICIAR_WINDOWS.bat para instalar os pacotes.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" configurar_ia.py
if errorlevel 1 (
  echo Configuracao nao concluida.
)
echo.
echo Para aplicar a configuracao, feche e abra INICIAR_WINDOWS.bat.
pause
