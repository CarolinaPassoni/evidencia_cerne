"""Configurador local e interativo, não transmite nem exibe a chave de API."""
from pathlib import Path
from getpass import getpass
from dotenv import set_key, dotenv_values

PATH=Path(__file__).resolve().parent/'.env'

def main():
    print('\nEVIDENCIA+ | CONFIGURAR INTELIGENCIA ARTIFICIAL')
    print('A chave e obtida por voce no seu provedor e pode gerar custos.')
    print('1 - Gemini\n2 - OpenAI\n3 - Somente modo basico (sem IA generativa)\n0 - Cancelar')
    option=input('Escolha: ').strip()
    if option=='0':
        return 0
    if option=='3':
        set_key(str(PATH),'AI_PROVIDER','none')
        print('Modo basico definido. Reinicie o servidor.')
        return 0
    if option not in ('1','2'):
        print('Opcao invalida.')
        return 1
    label='Gemini' if option=='1' else 'OpenAI'
    var='GEMINI_API_KEY' if option=='1' else 'OPENAI_API_KEY'
    print('A chave nao aparecera na tela enquanto voce digita ou cola.')
    key=getpass('Cole sua chave de API do '+label+': ').strip()
    if not key or len(key)<12 or any(c.isspace() for c in key):
        print('Chave vazia ou aparentemente invalida. Nenhuma alteracao feita.')
        return 1
    set_key(str(PATH),var,key)
    set_key(str(PATH),'AI_PROVIDER',label.lower())
    print('Provedor '+label+' selecionado. Reinicie o servidor.')
    print('A chave nao e verificada neste procedimento; a API pode exigir credito ou permissao.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
