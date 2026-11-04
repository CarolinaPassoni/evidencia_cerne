# Publicação no Render

Este pacote usa PostgreSQL para dados, fotos e documentos. O modelo DOCX original não foi alterado.

## Ambiente

- `DATABASE_URL`: **Internal Database URL** obtida em Render Dashboard > banco `evidencia-cerne-db` > Connections. Não divulgue a URL: ela contém senha.
- `SESSION_SECRET`: uma chave secreta longa, obrigatória para persistência e assinatura de sessão.
- `AI_ENCRYPTION_KEY`: chave Fernet base64 de 32 bytes para criptografar a API key no PostgreSQL.
- `ADMIN_EMAIL`: usuário administrador (padrão `admin@evidencias.local`).
- `ADMIN_PASSWORD`: senha forte, definida antes da primeira execução do banco.
- `COOKIE_HTTPS=1`, `OPEN_BROWSER=0`.
- Comando de início: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`.

## Atenção

- Plano gratuito do Render Postgres expira em 30 dias e **não faz backup automático**; não use produção institucional com dados reais nesse plano.
- Banco online começa vazio. Os registros do SQLite do Windows NÃO são migrados automaticamente. Faça migração separada após validar os dados e imagens.
- Fotos e documentos novos são gravados no PostgreSQL em BLOBs; adequado para homologação leve, mas para produção e escala recomenda-se armazenamento S3/R2 e banco PostgreSQL pago com backups.
- Não armazene `.env`, chaves ou banco SQLite no GitHub.
- A configuração de IA feita pelo painel é criptografada no banco e exige `AI_ENCRYPTION_KEY` estável em todos os deploys.


## Migração opcional dos registros locais

O banco criado no Render está vazio. Para levar os registros do Windows, faça backup completo da pasta `data`, obtenha a **External Database URL** no Render, autorize temporariamente o IP do seu computador na rede do banco e execute localmente `python migrar_sqlite_para_postgres.py --data-dir data`, com `DATABASE_URL` no ambiente. O script interrompe se o PostgreSQL já contiver dados ou se alguma foto/documento estiver ausente. Revogue o acesso externo ao terminar. Nunca compartilhe a URL de conexão nem publique arquivos de evidências no GitHub.
