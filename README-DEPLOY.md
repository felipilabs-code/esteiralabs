# Esteira Labs: deploy com Docker

A aplicação usa Flask para servir a interface e a API, e MySQL para guardar tarefas e projetos compartilhados. O container executa Flask por Gunicorn. O banco continua externo, então a hospedagem precisa permitir conexão de saída do container até o MySQL.

## Pré-requisitos

- Uma VPS ou hospedagem que aceite Docker Engine e Docker Compose.
- Um banco MySQL acessível pela hospedagem.
- Um domínio e um proxy reverso com HTTPS, além do controle de acesso aprovado pela TI.

Hospedagem cPanel compartilhada com **Setup Python App/Passenger**, mas sem Docker, deve continuar usando o fluxo Passenger descrito ao final deste documento.

## 1. Criar as tabelas

Crie um banco exclusivo para o MVP no painel autorizado pela TI. A aplicação espera que as tabelas existentes de `projects`, `tasks`, `task_assignees` e `task_topics` estejam nesse banco. Execute scripts de schema somente com a conta autorizada a administrá-lo; o usuário da aplicação não precisa de permissão para criar ou alterar tabelas.

O usuário da aplicação deve ter apenas `SELECT`, `INSERT`, `UPDATE` e `DELETE` no banco do MVP. A criação das tabelas é feita separadamente com a conta autorizada a administrá-lo.

## 2. Configurar as variáveis

Na pasta do projeto, crie o arquivo local `.env` a partir do exemplo e informe os dados fornecidos pela TI:

```sh
cp -n .env.example .env
```

Configure `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASSWORD`. `APP_PORT` define a porta local do proxy reverso e usa `8000` por padrão. O arquivo `.env` é excluído do Git e do contexto da imagem Docker; não coloque credenciais no código nem as envie ao repositório.

Gere um segredo exclusivo para assinar as sessões e configure `APP_SECRET_KEY`:

```sh
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Mantenha `SESSION_COOKIE_SECURE=true` em produção com HTTPS. `TRUST_PROXY_HEADERS=true` usa o cabeçalho `X-Real-IP` para aplicar o limite de tentativas ao IP real quando há um proxy confiável na frente do app; configure esse proxy para substituir o cabeçalho recebido do cliente. Para desenvolvimento local por HTTP, use `SESSION_COOKIE_SECURE=false` apenas no `.env` local.

## 3. Iniciar com Docker Compose

Na VPS, com Docker e Compose instalados e o `.env` configurado:

```sh
docker compose up --build -d
docker compose ps
docker compose logs -f web
```

O serviço fica disponível apenas em `127.0.0.1:8000` por padrão. Configure o proxy reverso aprovado pela TI para encaminhar o domínio à porta local e terminar HTTPS. Para usar outra porta local, ajuste `APP_PORT` no `.env` e recrie o serviço. Não exponha diretamente a porta da aplicação à internet.

Para publicar uma atualização:

```sh
docker compose up --build -d
```

Para parar o serviço:

```sh
docker compose down
```

Os dados ficam no MySQL externo e não são removidos ao recriar o container. O host MySQL precisa aceitar conexões originadas pela VPS/container; restrinja também essa permissão ao endereço e ao usuário da aplicação.

## 4. Login e proteção das rotas

A tabela `app_users` guarda os usuários e hashes de senha. Ela foi criada pela query inicial. Execute também `auth_login_attempts.sql` uma vez no banco para habilitar o limite de tentativas de login; o usuário MySQL da aplicação precisa de `SELECT`, `INSERT`, `UPDATE` e `DELETE` nessa tabela.

O Flask exige login para servir o quadro e para qualquer rota de tarefas ou projetos. As sessões expiram após oito horas, os formulários de escrita usam token CSRF e cinco tentativas incorretas por usuário e endereço de origem bloqueiam novas tentativas por 15 minutos. Os três perfis cadastrados identificam a pessoa e o papel; no momento, todos têm as mesmas permissões de edição.

## 5. Acesso da equipe

Antes de compartilhar a URL, habilite HTTPS e proteja o acesso à equipe. Não publique o sistema sem HTTPS. A senha inicial foi definida para cada pessoa; troque credenciais previsíveis antes de usar dados reais.

## Alternativa: cPanel com Python/Passenger

Se a hospedagem oferece **Setup Python App** e Python 3.9 ou superior, mas não Docker, configure o diretório da aplicação para a pasta que contém `app.py`, `passenger_wsgi.py` e `requirements.txt`; instale as dependências pelo painel. O ponto de entrada WSGI é `passenger_wsgi.py` e a variável WSGI é `application`.

Configure também `APP_SECRET_KEY` (com a chave aleatória gerada acima), `SESSION_COOKIE_SECURE=true` quando estiver usando HTTPS e `TRUST_PROXY_HEADERS=true` somente se o proxy confiável definir `X-Real-IP` corretamente.

Se o cPanel não oferecer Passenger nem Docker, não use o servidor de desenvolvimento do Flask como servidor público. Solicite à TI uma VPS administrada ou uma hospedagem que aceite aplicações Python WSGI.

## Arquivos principais

- `index.html`: interface do quadro e projetos.
- `app.py`: endpoints Flask para tarefas e projetos.
- `Dockerfile` e `compose.yaml`: imagem e execução do serviço web.
- `login.html`: tela de entrada.
- `auth_login_attempts.sql`: tabela para limitar tentativas incorretas.
- `passenger_wsgi.py`: entrada para cPanel/Passenger.
- `requirements.txt`: dependências Python, incluindo Gunicorn.
- As tabelas `projects`, `tasks`, `task_assignees` e `task_topics`: estrutura MySQL já usada pela aplicação.
