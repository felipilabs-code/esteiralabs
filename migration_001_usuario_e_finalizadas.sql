-- Execute uma vez no banco do MVP com uma conta administrativa.
-- Tarefas finalizadas: guarda quando a tarefa foi concluída (NULL = em andamento).
-- Se der erro "Duplicate column name 'completed_at'", a coluna já existe: ignore e siga para migration_002.

ALTER TABLE tasks
    ADD COLUMN completed_at TIMESTAMP NULL DEFAULT NULL AFTER due_date,
    ADD KEY ix_tasks_completed_at (completed_at);
