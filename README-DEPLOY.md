# Esteira Labs: deploy com Docker

A aplicação usa Flask para servir a interface e a API, e MySQL para guardar tarefas e projetos compartilhados. O container executa Flask por Gunicorn. O banco continua externo, então a hospedagem precisa permitir conexão de saída do container até o MySQL.

## Pré-requisitos

- Uma VPS ou hospedagem que aceite Docker Engine e Docker Compose.
- Um banco MySQL acessível pela hospedagem.
- Um domínio e um proxy reverso com HTTPS, além do controle de acesso aprovado pela TI.

Hospedagem cPanel compartilhada com **Setup Python App/Passenger**, mas sem Docker, deve continuar usando o fluxo Passenger descrito ao final deste documento.

## 1. Criar as tabelas

Crie um banco exclusivo para o MVP no painel autorizado pela TI. Se ainda não criou as tabelas, selecione esse banco e execute `schema.sql` e `auth_login_attempts.sql` com uma conta administrativa. Não rode esses scripts em outro banco. O usuário da aplicação não precisa de permissão para criar ou alterar tabelas.

Crie também pelo menos um registro de usuário em `app_users`, preenchendo `password_hash` com um hash Werkzeug PBKDF2-SHA256. Gere o hash localmente sem colocar a senha em um comando salvo no histórico:

```sh
python3 -c 'from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass("Senha: "), method="pbkdf2:sha256:600000"))'
```

Use o hash resultante em um `INSERT` administrativo para criar cada pessoa (com `UUID()` para o ID, nome de usuário, nome de exibição e perfil `Estagiário`, `Pessoa de Dados` ou `Líder`). Não use senha em texto simples nem uma senha inicial previsível. O usuário da aplicação deve ter apenas `SELECT`, `INSERT`, `UPDATE` e `DELETE` no banco do MVP.

## 2. Configurar as variáveis

Para executar localmente, crie o arquivo `.env` a partir do exemplo e informe os dados fornecidos pela TI:

```sh
cp -n .env.example .env
```

Configure `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASSWORD`. O arquivo `.env` é excluído do Git e do contexto da imagem Docker; não coloque credenciais no código nem as envie ao repositório.

Gere um segredo exclusivo para assinar as sessões e configure `APP_SECRET_KEY`:

```sh
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Mantenha `SESSION_COOKIE_SECURE=true` em produção com HTTPS. `TRUST_PROXY_HEADERS=true` usa o cabeçalho `X-Real-IP` para aplicar o limite de tentativas ao IP real quando há um proxy confiável na frente do app; configure esse proxy para substituir o cabeçalho recebido do cliente. Para desenvolvimento local por HTTP, use `SESSION_COOKIE_SECURE=false` apenas no `.env` local.

## 3. Deploy pelo Portainer

Antes do deploy, confirme com a TI que a rede Docker externa `ativaai` existe e que o container do Nginx Proxy Manager está conectado a ela. No Portainer, crie uma Stack usando o repositório Git, branch `main` e caminho `compose.yaml`. Cadastre nela `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` e `APP_SECRET_KEY` (gere este último com o comando acima). Não salve segredos no Git. O compose conecta o serviço `esteira-web` à rede `ativaai` e exige as variáveis antes de iniciar.

Depois do deploy, confirme que o container está `healthy`. No Nginx Proxy Manager, crie um Proxy Host para o domínio aprovado: encaminhamento `http` para `esteira-web`, porta `8000`. Ative SSL com Let's Encrypt, Force SSL e HTTP/2. Em Advanced, inclua `proxy_set_header X-Real-IP $remote_addr;`. O nome `esteira-web` evita conflito com serviços chamados `web` na mesma rede.

## 4. Iniciar localmente com Docker Compose

Na VPS, com Docker e Compose instalados e o `.env` configurado:

```sh
docker compose up --build -d
docker compose ps
docker compose logs -f esteira-web
```

O serviço não publica uma porta na VPS. O Nginx Proxy Manager acessa a porta interna 8000 pela rede Docker `ativaai`. Para testar em uma máquina local sem o proxy, adicione temporariamente um arquivo Compose de desenvolvimento que publique `127.0.0.1:8000:8000`. Não exponha diretamente a porta da aplicação à internet.

Para publicar uma atualização:

```sh
docker compose up --build -d
```

Para parar o serviço:

```sh
docker compose down
```

Os dados ficam no MySQL externo e não são removidos ao recriar o container. O host MySQL precisa aceitar conexões originadas pela VPS/container; restrinja também essa permissão ao endereço e ao usuário da aplicação.

## 5. Login e proteção das rotas

A tabela `app_users` guarda os usuários e hashes de senha. Crie-a com `schema.sql`. Execute também `auth_login_attempts.sql` uma vez no banco para habilitar o limite de tentativas de login; o usuário MySQL da aplicação precisa de `SELECT`, `INSERT`, `UPDATE` e `DELETE` nessa tabela.

O Flask exige login para servir o quadro e para qualquer rota de tarefas ou projetos. As sessões expiram após oito horas, os formulários de escrita usam token CSRF e cinco tentativas incorretas por usuário e endereço de origem bloqueiam novas tentativas por 15 minutos. Os três perfis cadastrados identificam a pessoa e o papel; no momento, todos têm as mesmas permissões de edição.

## 6. Acesso da equipe

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
- `schema.sql`: tabelas de usuários, projetos e tarefas.
- `passenger_wsgi.py`: entrada para cPanel/Passenger.
- `requirements.txt`: dependências Python, incluindo Gunicorn.
- As tabelas `projects`, `tasks`, `task_assignees` e `task_topics`: estrutura MySQL já usada pela aplicação.
