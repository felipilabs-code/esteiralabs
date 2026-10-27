"""API da Esteira Labs para Python/Flask e MySQL."""

import ipaddress
import os
import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pymysql
from flask import Flask, jsonify, redirect, request, send_from_directory, session, url_for
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
app = Flask(__name__)
app_secret_key = os.environ.get("APP_SECRET_KEY")
if not app_secret_key or len(app_secret_key) < 32:
    raise RuntimeError("Configure APP_SECRET_KEY com pelo menos 32 caracteres aleatórios antes de iniciar.")
app.config.update(
    SECRET_KEY=app_secret_key,
    MAX_CONTENT_LENGTH=64 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true",
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

STAGES = {"DEV", "HML", "PROD"}
AREAS = {"Dados", "Engenharia", "Análises", "Infraestrutura", "Outro"}
ASSIGNEES = {"Estagiário", "Pessoa de Dados", "Líder"}
DUMMY_PASSWORD_HASH = generate_password_hash(
    secrets.token_urlsafe(32), method="pbkdf2:sha256:600000"
)


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@app.errorhandler(ApiError)
def handle_api_error(error):
    return jsonify({"error": str(error)}), error.status


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception("Erro não tratado na API")
    return jsonify({"error": "Erro interno. Consulte os logs do servidor."}), 500


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_is_valid():
    expected = session.get("csrf_token", "")
    provided = request.headers.get("X-CSRF-Token", "")
    return bool(expected and provided and secrets.compare_digest(expected, provided))


@app.after_request
def prevent_private_response_caching(response):
    if request.path.startswith("/auth/") or request.path == "/api.php":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/login")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return send_from_directory(BASE_DIR, "login.html")


@app.get("/auth/csrf")
def auth_csrf():
    return jsonify({"csrfToken": csrf_token()})


@app.get("/auth/session")
def auth_session():
    if not session.get("user_id"):
        return jsonify({"error": "Autenticação necessária."}), 401
    return jsonify({
        "username": session.get("username", ""),
        "displayName": session.get("display_name", ""),
        "role": session.get("role", ""),
    })


@app.post("/auth/login")
def auth_login():
    if not csrf_is_valid():
        return jsonify({"error": "Sessão expirada. Atualize a página e tente novamente."}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Informe usuário e senha."}), 400
    username = data.get("username", "")
    password = data.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "Usuário ou senha inválidos."}), 401
    username = username.strip()
    if not username or len(username) > 40 or not password or len(password) > 256:
        return jsonify({"error": "Usuário ou senha inválidos."}), 401

    client_ip = request.remote_addr or "unknown"
    if os.environ.get("TRUST_PROXY_HEADERS", "false").lower() == "true":
        forwarded_ip = request.headers.get("X-Real-IP", "").strip()
        try:
            if forwarded_ip:
                client_ip = str(ipaddress.ip_address(forwarded_ip))
        except ValueError:
            client_ip = "unknown"
    client_ip = client_ip[:45]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    connection = db_connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT IGNORE INTO auth_login_attempts "
                "(username, ip_address, failed_attempts, window_started_at) "
                "VALUES (%s, %s, 0, UTC_TIMESTAMP())",
                (username, client_ip),
            )
            cursor.execute(
                "SELECT failed_attempts, window_started_at, blocked_until "
                "FROM auth_login_attempts WHERE username=%s AND ip_address=%s FOR UPDATE",
                (username, client_ip),
            )
            attempts = cursor.fetchone()
            if attempts["blocked_until"] and attempts["blocked_until"] > now:
                connection.commit()
                return jsonify({"error": "Muitas tentativas. Aguarde 15 minutos e tente novamente."}), 429
            cursor.execute(
                "SELECT id, username, display_name, role, password_hash "
                "FROM app_users WHERE username=%s AND is_active=1 LIMIT 1",
                (username,),
            )
            user = cursor.fetchone()
            password_hash = user["password_hash"] if user else DUMMY_PASSWORD_HASH
            password_matches = check_password_hash(password_hash, password)
            valid_login = bool(user and password_matches)
            if valid_login:
                cursor.execute(
                    "DELETE FROM auth_login_attempts WHERE username=%s AND ip_address=%s",
                    (username, client_ip),
                )
            else:
                window_start = attempts["window_started_at"]
                if now - window_start >= timedelta(minutes=15):
                    failures = 1
                    window_start = now
                else:
                    failures = attempts["failed_attempts"] + 1
                blocked_until = now + timedelta(minutes=15) if failures >= 5 else None
                cursor.execute(
                    "UPDATE auth_login_attempts SET failed_attempts=%s, window_started_at=%s, blocked_until=%s "
                    "WHERE username=%s AND ip_address=%s",
                    (failures, window_start, blocked_until, username, client_ip),
                )
            connection.commit()
    except pymysql.err.ProgrammingError as error:
        connection.rollback()
        if error.args and error.args[0] == 1146 and "auth_login_attempts" in str(error):
            raise ApiError(
                "Tabela de segurança ausente. Execute auth_login_attempts.sql no banco da aplicação.",
                503,
            ) from error
        raise
    finally:
        connection.close()

    if not valid_login:
        return jsonify({"error": "Usuário ou senha inválidos."}), 401

    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["display_name"] = user["display_name"]
    session["role"] = user["role"]
    return jsonify({"ok": True, "csrfToken": csrf_token()})


@app.post("/auth/logout")
def auth_logout():
    if not session.get("user_id"):
        return jsonify({"ok": True})
    if not csrf_is_valid():
        return jsonify({"error": "Sessão expirada. Atualize a página e tente novamente."}), 403
    session.clear()
    return jsonify({"ok": True})


def db_connect():
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ApiError("Configuração do banco incompleta no servidor.", 503)
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        connect_timeout=8,
    )


def read_json():
    if not request.is_json:
        raise ApiError("Envie os dados como application/json.")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Corpo JSON inválido.")
    return data


def required_text(data, field, max_length, label):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"{label} é obrigatório.")
    value = value.strip()
    if len(value) > max_length:
        raise ApiError(f"{label} excede {max_length} caracteres.")
    return value


def optional_text(data, field, max_length, label):
    value = data.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ApiError(f"{label} inválido.")
    value = value.strip()
    if len(value) > max_length:
        raise ApiError(f"{label} excede {max_length} caracteres.")
    return value


def task_values(data):
    title = required_text(data, "title", 160, "Título")
    description = optional_text(data, "description", 10000, "Descrição")
    repo = optional_text(data, "repo", 2048, "Link do repositório")
    if repo and not re.match(r"^https?://", repo, re.IGNORECASE):
        raise ApiError("O repositório deve começar com http:// ou https://.")
    area = required_text(data, "area", 40, "Área")
    if area not in AREAS:
        raise ApiError("Área inválida.")
    stage = required_text(data, "stage", 8, "Ambiente")
    if stage not in STAGES:
        raise ApiError("Ambiente inválido.")
    project_id = data.get("projectId") or None
    if project_id is not None and (not isinstance(project_id, str) or len(project_id) > 36):
        raise ApiError("Projeto inválido.")
    due = data.get("due") or None
    if due:
        try:
            date.fromisoformat(due)
        except (TypeError, ValueError):
            raise ApiError("Prazo inválido.")
    assignees = data.get("assignees", [])
    if not isinstance(assignees, list) or any(not isinstance(value, str) or value not in ASSIGNEES for value in assignees):
        raise ApiError("Responsáveis inválidos.")
    topics = data.get("topics", [])
    if not isinstance(topics, list) or any(not isinstance(value, str) for value in topics):
        raise ApiError("Tópicos inválidos.")
    topics = [value.strip() for value in topics if value.strip()]
    if len(topics) > 40 or any(len(value) > 300 for value in topics):
        raise ApiError("Cada tarefa pode ter até 40 tópicos de 300 caracteres.")
    return {
        "title": title,
        "description": description,
        "repo": repo,
        "project_id": project_id,
        "area": area,
        "stage": stage,
        "due_date": due,
        "assignees": list(dict.fromkeys(assignees)),
        "topics": topics,
    }


def task_output(connection, row):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT assignee FROM task_assignees WHERE task_id=%s ORDER BY position",
            (row["id"],),
        )
        assignees = [item["assignee"] for item in cursor.fetchall()]
        cursor.execute(
            "SELECT topic FROM task_topics WHERE task_id=%s ORDER BY position",
            (row["id"],),
        )
        topics = [item["topic"] for item in cursor.fetchall()]
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"] or "",
        "repo": row["repo"] or "",
        "projectId": row["project_id"] or "",
        "area": row["area"],
        "stage": row["stage"],
        "due": row["due_date"].isoformat() if row["due_date"] else "",
        "assignees": assignees,
        "topics": topics,
    }


def find_project(connection, project_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM projects WHERE id=%s", (project_id,))
        return cursor.fetchone()


@app.get("/")
def home():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api.php", methods=["GET", "POST", "PUT", "DELETE"])
def api():
    if not session.get("user_id"):
        return jsonify({"error": "Autenticação necessária."}), 401
    if request.method != "GET" and not csrf_is_valid():
        return jsonify({"error": "Sessão expirada. Atualize a página e tente novamente."}), 403

    resource = request.args.get("resource", "")
    item_id = request.args.get("id", "")
    if resource not in {"tasks", "projects"}:
        raise ApiError("Recurso inválido.", 404)

    connection = db_connect()
    try:
        if resource == "projects":
            result = projects_api(connection, item_id)
        else:
            result = tasks_api(connection, item_id)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def projects_api(connection, item_id):
    if request.method == "GET":
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name, description FROM projects ORDER BY created_at DESC")
            rows = cursor.fetchall()
        return jsonify([{"id": row["id"], "name": row["name"], "description": row["description"] or ""} for row in rows])

    if request.method in {"POST", "PUT"}:
        data = read_json()
        name = required_text(data, "name", 70, "Nome do projeto")
        description = optional_text(data, "description", 240, "Descrição")
        if request.method == "POST":
            project_id = str(uuid.uuid4())
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO projects (id, name, description) VALUES (%s, %s, %s)", (project_id, name, description))
            return jsonify({"id": project_id, "name": name, "description": description}), 201
        if not item_id:
            raise ApiError("Falta o ID do projeto.")
        with connection.cursor() as cursor:
            cursor.execute("UPDATE projects SET name=%s, description=%s WHERE id=%s", (name, description, item_id))
            if cursor.rowcount == 0 and not find_project(connection, item_id):
                raise ApiError("Projeto não encontrado.", 404)
        return jsonify({"id": item_id, "name": name, "description": description})

    raise ApiError("Método não permitido.", 405)


def tasks_api(connection, item_id):
    if request.method == "GET":
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM tasks ORDER BY updated_at DESC, created_at DESC")
            rows = cursor.fetchall()
        return jsonify([task_output(connection, row) for row in rows])

    if request.method == "POST":
        data = task_values(read_json())
        if data["project_id"] and not find_project(connection, data["project_id"]):
            raise ApiError("O projeto selecionado não existe.")
        task_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tasks (id, title, description, repo, project_id, area, stage, due_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (task_id, data["title"], data["description"], data["repo"], data["project_id"], data["area"], data["stage"], data["due_date"]),
            )
            replace_task_lists(cursor, task_id, data)
            cursor.execute("SELECT * FROM tasks WHERE id=%s", (task_id,))
            row = cursor.fetchone()
        return jsonify(task_output(connection, row)), 201

    if request.method == "PUT":
        if not item_id:
            raise ApiError("Falta o ID da tarefa.")
        data = task_values(read_json())
        if data["project_id"] and not find_project(connection, data["project_id"]):
            raise ApiError("O projeto selecionado não existe.")
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE tasks SET title=%s, description=%s, repo=%s, project_id=%s, area=%s, stage=%s, due_date=%s WHERE id=%s",
                (data["title"], data["description"], data["repo"], data["project_id"], data["area"], data["stage"], data["due_date"], item_id),
            )
            if cursor.rowcount == 0:
                cursor.execute("SELECT id FROM tasks WHERE id=%s", (item_id,))
                if not cursor.fetchone():
                    raise ApiError("Tarefa não encontrada.", 404)
            replace_task_lists(cursor, item_id, data)
            cursor.execute("SELECT * FROM tasks WHERE id=%s", (item_id,))
            row = cursor.fetchone()
        return jsonify(task_output(connection, row))

    if request.method == "DELETE":
        if not item_id:
            raise ApiError("Falta o ID da tarefa.")
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM tasks WHERE id=%s", (item_id,))
            if cursor.rowcount == 0:
                raise ApiError("Tarefa não encontrada.", 404)
        return jsonify({"ok": True})

    raise ApiError("Método não permitido.", 405)


def replace_task_lists(cursor, task_id, data):
    cursor.execute("DELETE FROM task_assignees WHERE task_id=%s", (task_id,))
    cursor.execute("DELETE FROM task_topics WHERE task_id=%s", (task_id,))
    for position, assignee in enumerate(data["assignees"]):
        cursor.execute(
            "INSERT INTO task_assignees (task_id, assignee, position) VALUES (%s, %s, %s)",
            (task_id, assignee, position),
        )
    for position, topic in enumerate(data["topics"]):
        cursor.execute(
            "INSERT INTO task_topics (task_id, topic, position) VALUES (%s, %s, %s)",
            (task_id, topic, position),
        )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), debug=False)
