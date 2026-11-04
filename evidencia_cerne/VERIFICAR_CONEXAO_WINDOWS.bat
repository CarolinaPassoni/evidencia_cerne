@echo off
setlocal
cd /d "%~dp0"
title Evidencia+ - Verificacao da conexao
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" verificar_conexao.py
) else (
  echo Ambiente Python ainda nao existe. Execute INICIAR_WINDOWS.bat primeiro.
  echo Abra INICIAR_WINDOWS.bat primeiro.
  pause
  exit /b 1
)
echo.
echo Se houver erro, envie uma foto DESTA JANELA, nao da tela de login.
pause
