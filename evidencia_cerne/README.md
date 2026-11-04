# Evidência+ | Plataforma de Registro Inteligente de Evidências (v1.5)

Aplicação web **executável**, em português do Brasil, para registrar atividades institucionais, montar até três grupos de registros fotográficos, consultar documentos CERNE e gerar evidências em **Word editável (.docx)** e **PDF**.

## Conclusão da implementação local | versão 1.5

Esta é a versão finalizada **para uso local no Windows ou Linux**. O Word padrão utiliza o **mesmo arquivo DOCX original enviado** como base, e as evidências são produzidas com os dados do formulário, as fotografias anexadas e o texto aprovado pelo usuário.

**Novidades:** campo de descrição e participantes para cada fotografia; exportação dessas legendas no Word/PDF quando preenchidas; botão de backup completo em **Minha conta** (administrador); configuração guiada da chave de IA com `CONFIGURAR_IA_WINDOWS.bat`; migração automática do banco de dados mantendo usuários e registros.

**Atualizar sem perder informações:** feche a aplicação e faça cópia da pasta `data`; descompacte o arquivo **`Atualizacao_Evidencia_CERNE_v1_5_Preservar_Dados.zip`** diretamente dentro da pasta `evidencia_cerne`, substituindo os arquivos existentes. O pacote de atualização não contém nem altera `data`, `.env` ou `.venv`. Inicie com `INICIAR_WINDOWS.bat` e use `Ctrl+F5` no navegador.

**Limite importante:** a versão 1.5 está pronta para instalar e usar localmente, mas **não está publicada em um servidor de produção**. Para uso público com múltiplos usuários, é necessário hospedagem segura, HTTPS, armazenamento durável para imagens, banco com backup externo e políticas de controle de acesso. A revisão generativa por IA continua dependendo de uma chave válida fornecida pelo usuário.

## Modelo DOCX original incorporado (v1.5)

O arquivo **`app/templates/modelo_original_evidencias.docx`** é agora o próprio documento Word enviado pelo usuário, incluído na distribuição. Na exportação usando **Modelo fiel ao documento enviado**, o Word é produzido a partir desse arquivo original: preserva papel, margens, estilos de parágrafo e formatação de títulos e listas. Todas as fotos e todos os textos demonstrativos são removidos e substituídos apenas pelas informações da atividade. A imagem original não é mantida como anexo invisível no novo DOCX.

O modelo pode ser baixado pelo botão **Baixar modelo DOCX original** na tela de Modelos de documentos. O gerador PDF segue o layout de referência, mas é renderizado separadamente, de forma que a tipografia e a paginação podem diferir do Word.

Para atualizar instalações antigas, siga as instruções da seção **Conclusão da implementação local | versão 1.5**. Não exclua `data`, `.env`, `.venv` nem as fotografias.

## Modelo de evidência (v1.3)

A exportação DOCX/PDF possui **Modelo fiel ao documento enviado**, selecionado por padrão. A estrutura segue a referência fornecida: título da atividade (com data, sem duplicá-la), descrição, **Registros 1, 2 e 3** com fotografias grandes na ordem definida, participantes em linhas separadas, objetivo, resultados, indicadores alcançados e competências e habilidades em tópicos. O modelo não inclui capa, cabeçalho decorativo nem seções numeradas.

Foram acrescentados dois campos editáveis ao cadastro: **Indicadores alcançados** e **Competências e habilidades**. Digite um indicador/competência por linha. Quando não forem preenchidos, a exportação exibe que a informação não foi cadastrada, sem inventar números ou resultados. A revisão por IA recebe esses campos e permanece sujeita à aprovação do usuário.

### Atualizar uma instalação existente (1.2)

1. Feche o servidor e copie a pasta `data` para backup.
2. Extraia **Atualizacao_Modelo_Word_Evidencia_v1_3.zip** na pasta raiz `evidencia_cerne`, preservando `data/`, `.env` e `.venv/`.
3. Execute `INICIAR_WINDOWS.bat`, use `Ctrl+F5` no navegador e abra uma atividade.
4. Preencha os novos campos, selecione **Modelo fiel ao documento enviado**, aprove o registro e exporte.

Na inicialização, o sistema adiciona **somente as colunas novas** à tabela de atividades e o campo de identificação do layout à tabela de modelos. Fotos, atividades e credenciais antigas são preservadas. O modelo institucional anterior continua disponível no seletor, caso seja necessário.

**Observação:** o exemplo gerado utiliza a fotografia ilustrativa do documento enviado apenas para demonstrar a formatação. Os documentos reais usam exclusivamente as fotos anexadas em cada atividade.

## Correção de conexão (v1.2)

O erro **Failed to fetch** aponta para perda de comunicação do navegador com o servidor e **não é indicação de senha errada**. Nesta versão, `INICIAR_WINDOWS.bat` só abre o navegador depois de a API responder. Deixe a janela do servidor aberta enquanto estiver utilizando a plataforma.

Se o problema continuar, execute `VERIFICAR_CONEXAO_WINDOWS.bat` ou tente acessar `http://127.0.0.1:8000/api/health`. Uma resposta `{"ok":true,"app":"evidencia_cerne",...}` confirma que o back-end está disponível. Em caso de porta ocupada, feche outras janelas do servidor; se for necessário, escolha outra porta no `.env`. Para aplicar a correção sobre uma instalação existente, substitua somente os arquivos do pacote de correção, sem apagar `data`, `.env` ou `.venv`.

## 1. Primeiro acesso no Windows

1. Instale o **Python 3.11 ou superior** (marque a opção **Add Python to PATH**, ou instale o Python Launcher `py`).
2. Extraia o ZIP **em uma pasta local**. Não execute dentro do ZIP.
3. Abra `INICIAR_WINDOWS.bat`. No primeiro uso, as dependências Python serão instaladas. É necessária conexão com a internet **apenas para instalar pacotes e para usar IA/voz online**.
4. Abra **http://127.0.0.1:8000** no navegador.
5. Para a primeira entrada, abra `data/ACESSO_INICIAL.txt`, que o sistema cria automaticamente. Copie login e senha. **Altere a senha** no menu Minha conta. O arquivo temporário de credenciais é apagado após a alteração.

**Se aparecer "Login ou senha incorretos":** confirme o e-mail escrito dentro de `data/ACESSO_INICIAL.txt`, que pode ser diferente do e-mail do exemplo. Se você alterou as variáveis `ADMIN_EMAIL` e `ADMIN_PASSWORD` depois da primeira execução, isso **não muda a conta existente no banco**. Para redefinir a senha de um usuário que já existe, feche o sistema e execute `REDEFINIR_ACESSO_WINDOWS.bat`. O programa mostrará os e-mails cadastrados e solicitará uma senha nova com no mínimo 12 caracteres. **Esse procedimento não apaga atividades, projetos nem fotos.**

O sistema guarda os dados na pasta `data`. Para não perder suas evidências, **faça backup dessa pasta**.

## 2. Primeiro acesso no Linux / macOS

```bash
cd evidencia_cerne
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python iniciar.py
```

Acesse http://127.0.0.1:8000 e consulte `data/ACESSO_INICIAL.txt` na primeira execução. Se usar macOS, `python3` deve ser Python 3.11+.

## 3. Docker (opcional)

```bash
docker compose up --build -d
```

Abra `http://127.0.0.1:8000`. O arquivo de credenciais inicial estará em `data/ACESSO_INICIAL.txt` no host. O volume `data` é persistente.

## 4. Configurar a Inteligência Artificial

Sem chave de API, a plataforma **continua funcional**, mas opera em **modo básico**: cadastro, transcrição pelo navegador compatível, interpretação simples de relatos, salvamento, fotos, prévia e documentos. **Modo básico não é IA generativa.**

O aplicativo carrega automaticamente o arquivo `.env` **na pasta raiz do projeto**. Copie `.env.exemplo` para `.env`, edite os valores e reinicie o programa. As variáveis do sistema têm prioridade sobre as do arquivo. Não insira suas chaves em páginas HTML ou repositórios públicos.

`ADMIN_EMAIL` e `ADMIN_PASSWORD` servem **somente para criar a primeira conta quando o banco estiver vazio**. Eles não redefinem senhas de usuários existentes. Nesse caso, use `REDEFINIR_ACESSO_WINDOWS.bat`.

Para ativar a revisão generativa e a análise opcional de fotografias no Windows, execute **`CONFIGURAR_IA_WINDOWS.bat`**, informe seu provedor e sua própria chave de API, depois reinicie a plataforma. A chave é gravada apenas no arquivo local `.env`. Também é possível configurar manualmente **um** dos provedores:

**Gemini** (prioridade se houver duas chaves configuradas):

```powershell
# PowerShell: abra um terminal na pasta do projeto
$env:GEMINI_API_KEY="SUA_CHAVE_AQUI"
$env:GEMINI_MODEL="gemini-2.5-flash"
python iniciar.py
```

**OpenAI**:

```powershell
$env:OPENAI_API_KEY="SUA_CHAVE_AQUI"
$env:OPENAI_MODEL="gpt-4o-mini"
python iniciar.py
```

A lista de modelos disponíveis depende da sua conta e das condições dos provedores; o modelo pode ser alterado sem mudar o código. As chaves ficam **apenas no servidor**, nunca nos arquivos estáticos. Para escolher o provedor quando há duas chaves, configure `AI_PROVIDER=gemini` ou `AI_PROVIDER=openai` no `.env`. `AI_PROVIDER=none` desativa recursos generativos.

Os textos enviados à revisão por IA e os documentos recuperados para fundamentação serão processados pelo provedor configurado. As fotografias **só são enviadas ao provedor** quando o usuário escolhe **Sugerir descrições pelas fotos** e confirma a ação. Verifique autorizações, especialmente com imagens de estudantes.

## 4.1. Configurar chave da IA dentro da plataforma (novo na v1.6)

Entre como administrador e abra **Configurar IA** no menu esquerdo. Selecione **Google Gemini** ou **OpenAI**, cole sua chave de API, confirme o nome do modelo e clique **Salvar configuração**. Depois, clique **Testar conexão com IA**. A chave fica gravada em `data/.ai_credentials.enc` usando criptografia Fernet; a chave local de criptografia fica em `data/.ai_credentials.key`. A interface **nunca devolve a chave completa**. Por segurança, os dois arquivos não entram no download de backup dos registros. Se reinstalar/migrar de máquina, preserve esses dois arquivos com cuidado ou recadastre a chave.

No primeiro uso após atualizar, o inicializador detecta se a biblioteca `cryptography` falta na instalação e a instala. **Não é preciso editar o `.env`** para cadastrar a chave. Variáveis antigas do `.env` continuam funcionando enquanto nenhuma configuração for salva pelo painel. Uma configuração salva tem prioridade sobre o `.env`. Apenas administradores podem alterar ou testar a chave; usuários comuns podem utilizar a IA já configurada.

Para **sair da plataforma**, use **Sair da plataforma** no rodapé do menu esquerdo. Alterações pendentes são salvas antes de encerrar a sessão; no fim, a sessão é invalidada no servidor.

A função de ditado depende do suporte do navegador à Web Speech API, de microfone autorizado e, em ambientes publicados, de HTTPS. O reconhecimento pode usar serviço externo do fabricante do navegador. A plataforma envia à IA somente os textos do relato quando você solicita interpretação/revisão, conforme o serviço escolhido. Para dados de alunos e fotos, confirme as autorizações necessárias.

## 5. Cadastro CERNE e RAG

Em **Base CERNE**, adicione manualmente referências ou importe arquivos **PDF, DOCX, TXT ou MD**. O sistema extrai o texto, cria trechos e consulta os mais relacionados à atividade pela pesquisa textual FTS5 do SQLite, antes de preparar um texto com IA. É uma primeira versão de **RAG com busca lexical**, não uma busca vetorial com embeddings.

Marque **Referência verificada** apenas quando houver conferência com uma publicação autorizada, anotando edição, fonte e ano. **Nenhuma prática ou indicador do CERNE é presumido por padrão.** A IA recebe instruções para distinguir orientação de fatos comprovados. O usuário precisa conferir as sugestões.

PDF digitalizado como imagem requer OCR antes da importação. O sistema não inventa evidências que faltam nem certifica aderência ao CERNE.

## 6. Fluxo de uso

1. Cadastre um projeto (opcional) e abra **Criar evidência**.
2. Clique em **Falar e preencher tudo**, descreva a atividade de uma vez e pare o microfone. Os campos vazios serão preenchidos automaticamente com as informações identificadas. O que não foi informado não será inventado. A IA configurada melhora a extração; sem chave existe um modo básico limitado.
3. Para ditar apenas um campo, use o botão **🎙** ao lado dele. Funciona em título, data, local, participantes, descrições, objetivos, resultados, indicadores, competências, projeto e registros fotográficos. Também é possível digitar o relato e clicar **Interpretar relato** para revisar sugestões antes de aplicá-las.
4. Preencha data, local, título, descrição, objetivo e resultados. Registre também indicadores e competências, um item por linha, e acrescente considerações finais apenas se utilizar o modelo institucional antigo.
5. Anexe fotografias aos **três grupos** disponíveis, edite as descrições e use as setas para alterar sua ordem.
6. Clique **Revisar texto** para obter sugestões. Se IA estiver configurada, é possível também pedir descrições das fotografias mediante consentimento.
7. **Aprove a evidência** depois de conferir tudo. Os campos título, descrição, objetivo e resultados são obrigatórios para exportar. Os demais permanecem visíveis como “Não informado” quando vazios.
8. Escolha **Modelo fiel ao documento enviado** (selecionado por padrão) ou o modelo institucional antigo e clique **Word .docx** ou **PDF**. Os arquivos ficarão em **Documentos**.

As alterações de texto são salvas automaticamente no banco depois de um curto intervalo sem digitar. Fotos são enviadas imediatamente. O histórico de edições fica no banco de dados.

## 7. Arquitetura

```text
Navegador (HTML/CSS/JavaScript)
  ├── Reconhecimento de voz nativo (Web Speech API, quando disponível)
  └── API REST JSON (FastAPI)
       ├── Sessões autenticadas + CSRF
       ├── Atividades, projetos, pessoas e componentes (SQLAlchemy)
       ├── Fotos (Pillow, validação de arquivo e conversão JPEG)
       ├── Banco relacional SQLite + pesquisa FTS5
       ├── Recuperação RAG da base CERNE
       ├── Gemini/OpenAI (chaves opcionais no servidor)
       ├── Gerador DOCX (python-docx)
       └── Gerador PDF (ReportLab)

Pasta `data/`
  ├── .ai_credentials.enc e .ai_credentials.key (configurações privadas da IA)
  ├── evidencias.db (registros, índices, histórico)
  ├── uploads/ (fotografias privadas)
  ├── documents/ (Word e PDF gerados)
  └── .session_key (segredo de sessão local)
```

Arquivos importantes: `app/main.py` (API), `app/models.py` (tabelas), `app/agent.py` (IA), `app/knowledge.py` (RAG), `app/documents.py` (Word/PDF), `app/static/` (interface), `tests/` (testes).

## 8. Segurança e limites

- O primeiro administrador recebe uma senha aleatória se `ADMIN_PASSWORD` não for definida na criação inicial do banco. **Não compartilhe** o arquivo `ACESSO_INICIAL.txt`.
- A aplicação inicia apenas em `127.0.0.1` no computador local. **Não exponha diretamente a porta 8000 à internet**.
- Para uso online, configure HTTPS, `COOKIE_HTTPS=1`, `SESSION_SECRET` fixo e longo, controle de acesso por rede ou proxy reverso, política de backups, proteção de dados pessoais e políticas de retenção de arquivos.
- **Essa entrega é uma versão funcional inicial de instância única**, não um serviço já publicado e dimensionado para várias máquinas. SQLite e o armazenamento local exigem um volume persistente e não suportam escalabilidade horizontal imediata. O código aceita `DATABASE_URL` para outro banco SQL, mas PostgreSQL em produção exige instalar o driver apropriado, elaborar migrações e manter armazenamento de imagens/documentos persistente ou migrar para S3.
- O banco contém histórico de alterações. Para conformidade institucional, acrescente política de retenção, logs de acesso, autorização granular por projeto e backups externos antes do uso com dados sensíveis.
- O reconhecimento de voz depende de Chrome/Edge ou outro navegador compatível, permissão do microfone e, conforme a implementação, conexão com serviço externo. Não é garantido em todos os navegadores.
- Nenhuma chave de IA é fornecida neste pacote. **Recursos generativos exigem sua própria chave e podem ter custo**.
- São permitidas até **25 fotografias em cada um dos três grupos**, com no máximo **15 por envio** e **12 MB por imagem**.

## 9. Testes

A v1.6 inclui testes para o cadastro de chave criptografada, restrição administrativa, logout, preenchimento básico dos relatos e seleção da credencial correta nos pedidos aos provedores. O fluxo da interface foi conferido com um navegador automatizado e respostas simuladas; o reconhecimento de áudio real depende do navegador e do microfone de cada máquina. A conexão real com Gemini/OpenAI precisa ser verificada com a chave do usuário.

```bash
python -m pytest -q tests/
```

Os testes verificam autenticação/CSRF, cadastro, pesquisa CERNE, grupos e ordem de fotografias, geração de DOCX e PDF, duplicação, exclusão e histórico. Os testes utilizam banco temporário isolado.

## 10. Como publicar depois

Recomendação: hospede em um servidor com Docker, volume persistente de dados, HTTPS e backups. Não faça deploy em armazenamento efêmero sem migrar imagens e documentos para armazenamento externo. O código pode ser adaptado para infraestrutura gerenciada, mas **nenhuma hospedagem é realizada automaticamente nesta entrega**.


## Neon PostgreSQL + Render

Veja `NEON_RENDER_GUIA.md` e use `validar_conexao_neon.py` antes de publicar.
