-- database/init.sql - Healthcare API Gateway Database Initialization
-- Versión simplificada para SQLite y SQL Server

-- ============================================================================
-- CREATE TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token VARCHAR(255) NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    revoked_at DATETIME,
    revoked_by INTEGER,
    last_used_at DATETIME,
    total_requests INTEGER DEFAULT 0,
    total_tokens_consumed INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (revoked_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    token_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    total_messages INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    tools_used TEXT,
    prompt_modes_used TEXT,
    language_detected VARCHAR(10),
    FOREIGN KEY (token_id) REFERENCES tokens(id)
);

CREATE TABLE IF NOT EXISTS api_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id INTEGER NOT NULL,
    session_id INTEGER,
    endpoint VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL,
    request_data TEXT,
    response_status INTEGER NOT NULL,
    response_data TEXT,
    tokens_consumed INTEGER DEFAULT 0,
    processing_time REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    tool_used VARCHAR(50),
    prompt_mode VARCHAR(50),
    language_detected VARCHAR(10),
    estimated_cost_usd REAL DEFAULT 0.0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    FOREIGN KEY (token_id) REFERENCES tokens(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- ============================================================================
-- CREATE INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_tokens_token ON tokens(token);
CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_api_requests_token_id ON api_requests(token_id);

-- ============================================================================
-- INSERT DEFAULT DATA
-- ============================================================================

-- Admin user
INSERT OR IGNORE INTO users (username, email, role, is_active, created_at)
VALUES ('admin', 'admin@healthcare.local', 'admin', 1, datetime('now'));

-- Doctor user
INSERT OR IGNORE INTO users (username, email, role, is_active, created_at, created_by)
SELECT 'doctor1', 'doctor1@example.com', 'user', 1, datetime('now'), u.id
FROM users u WHERE u.username = 'admin';

-- Monitor user
INSERT OR IGNORE INTO users (username, email, role, is_active, created_at, created_by)
SELECT 'monitor1', 'monitor1@example.com', 'monitor', 1, datetime('now'), u.id
FROM users u WHERE u.username = 'admin';

-- ============================================================================
-- INSERT PREDEFINED TOKENS (from admin guide)
-- ============================================================================

-- Admin token
INSERT OR IGNORE INTO tokens (token, user_id, name, status, created_at, total_requests, total_tokens_consumed)
SELECT 
    'hcg_gomedisys_admin_9120B76F636BE172',
    u.id,
    'Admin Management Token',
    'active',
    datetime('now'),
    0,
    0
FROM users u 
WHERE u.username = 'admin'
  AND NOT EXISTS (SELECT 1 FROM tokens t WHERE t.token = 'hcg_gomedisys_admin_9120B76F636BE172');

-- Demo doctor token
INSERT OR IGNORE INTO tokens (token, user_id, name, status, created_at, total_requests, total_tokens_consumed)
SELECT 
    'hcg_gomedisys_user_demo_8025A4507BCBD1D1',
    u.id,
    'Demo Doctor Token',
    'active',
    datetime('now'),
    0,
    0
FROM users u 
WHERE u.username = 'doctor1'
  AND NOT EXISTS (SELECT 1 FROM tokens t WHERE t.token = 'hcg_gomedisys_user_demo_8025A4507BCBD1D1');

-- Monitor token
INSERT OR IGNORE INTO tokens (token, user_id, name, status, created_at, total_requests, total_tokens_consumed)
SELECT 
    'hcg_gomedisys_monitor_32B581AA6DA7442D',
    u.id,
    'System Monitor Token',
    'active',
    datetime('now'),
    0,
    0
FROM users u 
WHERE u.username = 'monitor1'
  AND NOT EXISTS (SELECT 1 FROM tokens t WHERE t.token = 'hcg_gomedisys_monitor_32B581AA6DA7442D');