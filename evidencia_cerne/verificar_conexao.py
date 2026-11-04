"""Checks running backend, verifies identity and gives user-friendly hints."""
import json
import os
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env', override=False)
port = os.getenv('PORT', '8000')
url = f'http://127.0.0.1:{port}'
print('\nEVIDENCIA+ | Verificacao de conexao')
print('Pasta:', ROOT)
print('Endereco:', url)
print('Banco:', ROOT / 'data' / 'evidencias.db')
print('Banco encontrado:', 'SIM' if (ROOT / 'data' / 'evidencias.db').is_file() else 'NAO')
try:
    with urlopen(url + '/api/health', timeout=4) as reply:
        data = json.load(reply)
        if data.get('app') == 'evidencia_cerne':
            print('\nSUCESSO! API da plataforma esta conectada e respondendo.')
            print('Abra ' + url + ' e atualize com Ctrl+F5.')
        else:
            print('\nATENCAO: outro programa responde nesse endereco.')
            print('Resposta:', data)
except HTTPError as error:
    print(f'\nERRO HTTP {error.code}.')
    if error.code == 404:
        print('Pode ser uma versao antiga da plataforma em execucao.')
    print('Feche a janela antiga do servidor e execute INICIAR_WINDOWS.bat.')
except (URLError, TimeoutError, ConnectionError) as error:
    print('\nSEM CONEXAO: o servidor nao esta disponivel.')
    print('Execute INICIAR_WINDOWS.bat e deixe a janela preta aberta.')
    print('Se o erro persistir, fotografe a mensagem na janela preta.')
    print('Detalhe:', type(error).__name__, str(error))
