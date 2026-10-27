CREATE TABLE IF NOT EXISTS auth_login_attempts (
    username VARCHAR(40) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    ip_address VARCHAR(45) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    failed_attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
    window_started_at DATETIME NOT NULL,
    blocked_until DATETIME NULL,
    PRIMARY KEY (username, ip_address),
    KEY ix_auth_login_attempts_blocked_until (blocked_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
