"""Start the Evidência+ API; only open browser after health-check succeeds."""
import os
import socket
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import uvicorn
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env', override=False)
HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', '8000'))
BROWSER_URL = f'http://127.0.0.1:{PORT}'


def check_server():
    try:
        with urlopen(BROWSER_URL + '/api/health', timeout=0.5) as res:
            import json
            data = json.load(res)
            return res.status == 200 and data.get('app') == 'evidencia_cerne'
    except (OSError, URLError, HTTPError, ValueError):
        return False


def port_in_use():
    try:
        with socket.create_connection(('127.0.0.1', PORT), timeout=0.5):
            return True
    except OSError:
        return False


def open_browser():
    if os.getenv('OPEN_BROWSER', '1') != '0':
        try:
            webbrowser.open(BROWSER_URL)
        except Exception as exc:
            print(f'Navegador nao foi aberto automaticamente: {exc}', flush=True)


def await_ready():
    for _ in range(100):
        if check_server():
            print('\nSERVIDOR ATIVO: ' + BROWSER_URL, flush=True)
            open_browser()
            return
        time.sleep(0.2)
    print('\nAVISO: servidor ainda nao respondeu. Execute VERIFICAR_CONEXAO_WINDOWS.bat.', flush=True)


def main():
    print('\nEVIDENCIA+ | Inicializador v1.6', flush=True)
    print('Endereco: ' + BROWSER_URL, flush=True)
    if port_in_use():
        if check_server():
            print('O Evidencia+ ja esta aberto nesta porta. Abra o navegador para utiliza-lo.', flush=True)
            open_browser()
            return 0
        print(f'\nERRO: porta {PORT} ja utilizada por outro processo ou versao antiga.', flush=True)
        print('Feche outras janelas do servidor e execute o inicializador novamente.', flush=True)
        print('Se for necessario, defina PORT=8001 no .env e reinicie.', flush=True)
        return 2
    threading.Thread(target=await_ready, daemon=True).start()
    try:
        uvicorn.run('app.main:app', host=HOST, port=PORT, reload=False, proxy_headers=False)
    except Exception as exc:
        print(f'\nERRO AO INICIAR: {type(exc).__name__}: {exc}', flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
