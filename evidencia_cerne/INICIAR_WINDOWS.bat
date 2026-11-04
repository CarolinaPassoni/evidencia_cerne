@echo off
setlocal
cd /d "%~dp0"
title Evidencia+ - Servidor (MANTENHA ESTA JANELA ABERTA)
echo.
echo ===============================================
echo  EVIDENCIA+  -  INICIAR PLATAFORMA
echo ===============================================
echo.
if not exist ".venv\Scripts\python.exe" (
  echo Preparando Python na primeira execucao...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale Python 3.11 ou superior.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -c "import fastapi,uvicorn,sqlalchemy,dotenv,docx,PIL,pypdf,reportlab,cryptography" >nul 2>nul
if errorlevel 1 (
  echo Instalando dependencias. A primeira instalacao precisa de internet...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo ERRO: falha ao instalar os pacotes. Consulte a mensagem acima.
    pause
    exit /b 1
  )
)
echo A janela abaixo e o servidor. Nao a feche durante o uso.
echo O navegador sera aberto somente quando o servidor responder.
echo.
".venv\Scripts\python.exe" iniciar.py
if errorlevel 1 (
  echo.
  echo Falha ao iniciar. Execute VERIFICAR_CONEXAO_WINDOWS.bat e fotografe o resultado.
)
echo.
echo Servidor finalizado. Para usar novamente, execute este arquivo.
pause
