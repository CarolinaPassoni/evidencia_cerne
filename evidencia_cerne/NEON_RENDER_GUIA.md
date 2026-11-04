# Evidência+ com Neon PostgreSQL e Render

## Situação desta entrega

Este pacote **está preparado** para conectar o site Evidência+ ao Neon, mas não contém credenciais, não cria o banco Neon e não publica o site automaticamente. É necessário conectar a conta Neon ao ChatGPT ou criar o projeto pelo painel do Neon; a publicação no Render também depende de um repositório Git acessível para implantação.

## 1. Criar o banco no Neon

1. No Neon, crie um projeto PostgreSQL chamado `evidencia-cerne` na região preferida, se disponível.
2. No painel do projeto, copie a connection string PostgreSQL **com SSL**. Ela tem formato semelhante a:
   `postgresql://USUARIO:SENHA@HOST/neondb?sslmode=require`
3. Não envie a senha em mensagens, documentos públicos ou GitHub. Cole a URL **somente como variável de ambiente protegida** no Render.
4. O plano gratuito não tem data fixa de expiração, mas tem cotas e pode mudar. Mantenha backups independentes.

## 2. Publicar o servidor no Render

1. Publique os arquivos deste ZIP em um **repositório privado** GitHub (sem `.env`, sem `data/` real, nem credenciais).
2. No Render, crie um Web Service Python apontando para o repositório, com:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`
   - Health check: `/api/health`
3. Configure as variáveis secretas no painel de ambiente do serviço:

   | Variável | Valor |
   |---|---|
   | `DATABASE_URL` | URL privada do PostgreSQL Neon, com `sslmode=require` |
   | `SESSION_SECRET` | texto aleatório forte (mínimo 32 bytes de entropia) |
   | `AI_ENCRYPTION_KEY` | chave Fernet 32 bytes codificada em URL-safe Base64 |
   | `ADMIN_EMAIL` | e-mail desejado para login inicial |
   | `ADMIN_PASSWORD` | senha forte exclusiva, preferencialmente 16+ caracteres |
   | `COOKIE_HTTPS` | `1` |
   | `OPEN_BROWSER` | `0` |

   Gere `AI_ENCRYPTION_KEY` localmente com:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

4. Faça o deploy, espere o status disponível e confira `/api/health`. Em seguida, faça login e gere uma evidência de teste.
5. **Não altere** `SESSION_SECRET` ou `AI_ENCRYPTION_KEY` depois da publicação sem plano de migração, pois sessões e a chave salva da IA serão afetadas.

## 3. Testar o Neon sem exibir a senha

Com a variável `DATABASE_URL` definida no computador onde vai testar, rode:
`python validar_conexao_neon.py`

O verificador usa uma consulta somente de leitura e não cria tabelas nem modifica dados.

## 4. Migrar as evidências locais (se houver dados)

1. Faça backup da pasta `data/` inteira do Windows, especialmente `evidencias.db`, `uploads/` e `documents/`.
2. Execute o script `migrar_sqlite_para_postgres.py` **antes do primeiro início do aplicativo remoto**, pois o primeiro início cria um usuário e modelos no banco novo, impedindo a migração automática para banco não vazio.
3. Use uma conexão direta Neon com SSL. Ajuste as permissões de rede conforme a conta e execute o script localmente, sem compartilhar a conexão.
4. Depois, confira quantidades de atividades, fotos e documentos e abra registros de amostra. Só então considere encerrar o banco anterior.
5. A configuração local da chave de IA **não é migrada automaticamente**: recadastre a chave no menu "Configurar IA" do ambiente online.

**Observação:** fotos e DOCX/PDF são armazenados como dados binários no PostgreSQL nesta versão, portanto também consomem a cota gratuita do Neon. Quando o volume crescer, mover anexos para armazenamento de objetos é recomendável. O banco gratuito não substitui um backup.

## 5. O que não foi alterado

O arquivo `app/templates/modelo_original_evidencias.docx` permanece exatamente igual ao modelo aprovado. Cadastro de atividades, ditado por voz, três grupos fotográficos, configurações de IA e sair da sessão permanecem preservados.
