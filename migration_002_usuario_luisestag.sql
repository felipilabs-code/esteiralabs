-- Novo estagiário: luisestag (senha armazenada apenas como hash PBKDF2-SHA256).
-- O id é omitido para o banco gerar o valor (a coluna app_users.id é numérica neste banco).

INSERT INTO app_users (username, display_name, role, password_hash)
VALUES (
    'luisestag',
    'Luis Estagiário',
    'Estagiário',
    'pbkdf2:sha256:600000$5RH928tjb4Ey0tfL$3fff85a33e5aede0a9c4bb498ac0cac0f88c08abb6e22ba96324c1c6518752f7'
)
ON DUPLICATE KEY UPDATE
    password_hash = VALUES(password_hash),
    display_name = VALUES(display_name),
    role = VALUES(role),
    is_active = 1;
