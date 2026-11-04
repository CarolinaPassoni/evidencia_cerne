# Publicação no Render e Neon

Este serviço usa autenticação própria com sessão assinada e registro revogável no banco. Não utiliza Neon Auth, mesmo que esse recurso esteja habilitado no projeto Neon.

Fotos, documentos e configuração criptografada da IA ficam no PostgreSQL. Arquivos de dados locais e credenciais não são incluídos nesta branch. Não há migração automática dos dados do computador.

A sessão tem duração máxima de 12 horas. Logout revoga a sessão no banco. Trocar a senha revoga outras sessões; redefinição local revoga todas. Há limite de 20 tentativas de login por IP a cada cinco minutos no processo único. Escala para múltiplos processos requer limite compartilhado.

O acesso aos registros é compartilhado entre usuários autenticados. Não há cadastro público ou isolamento por projeto. A instalação inicia com apenas uma conta administrativa. Não crie contas para pessoas que não possam acessar os mesmos registros.

Segredos são configurados somente no ambiente do Render: DATABASE_URL, SESSION_SECRET, AI_ENCRYPTION_KEY e ADMIN_PASSWORD. COOKIE_HTTPS=1 é obrigatório na publicação. Mantenha as chaves de assinatura e criptografia estáveis.

O serviço gratuito pode suspender por inatividade. Recursos de IA exigem chave própria no menu Configurar IA. O banco e anexos consomem a cota do Neon. Preserve backups externos.
