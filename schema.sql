-- Execute uma vez no banco labs_esteira_mvp com uma conta administrativa.
-- A conta de execução da aplicação não precisa de privilégios DDL.

CREATE TABLE IF NOT EXISTS app_users (
    id CHAR(36) NOT NULL,
    username VARCHAR(40) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    role VARCHAR(40) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_app_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS projects (
    id CHAR(36) NOT NULL,
    name VARCHAR(70) NOT NULL,
    description VARCHAR(240) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_projects_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tasks (
    id CHAR(36) NOT NULL,
    title VARCHAR(160) NOT NULL,
    description TEXT NOT NULL,
    repo VARCHAR(2048) NOT NULL DEFAULT '',
    project_id CHAR(36) NULL,
    area VARCHAR(40) NOT NULL,
    stage ENUM('DEV', 'HML', 'PROD') NOT NULL DEFAULT 'DEV',
    due_date DATE NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_tasks_project_id (project_id),
    KEY ix_tasks_stage_area (stage, area),
    KEY ix_tasks_updated_at (updated_at),
    CONSTRAINT fk_tasks_project FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS task_assignees (
    task_id CHAR(36) NOT NULL,
    assignee VARCHAR(40) NOT NULL,
    position SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (task_id, assignee),
    KEY ix_task_assignees_position (task_id, position),
    CONSTRAINT fk_task_assignees_task FOREIGN KEY (task_id)
        REFERENCES tasks (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS task_topics (
    task_id CHAR(36) NOT NULL,
    position SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    topic VARCHAR(300) NOT NULL,
    PRIMARY KEY (task_id, position),
    CONSTRAINT fk_task_topics_task FOREIGN KEY (task_id)
        REFERENCES tasks (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
