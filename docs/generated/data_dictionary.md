
**`api_usage`**: AI provider call log used for usage statistics.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | indexed |
| `provider` | VARCHAR | no |  |
| `kind` | VARCHAR | no |  |
| `tokens_est` | INTEGER | no |  |
| `latency_ms` | FLOAT | no |  |
| `ok` | BOOLEAN | no |  |
| `created_at` | DATETIME | no |  |

**`audit_logs`**: Audit trail of every sensitive action with user, entity, details, IP and request id.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | yes | indexed |
| `user_id` | VARCHAR | yes |  |
| `user_email` | VARCHAR | yes |  |
| `action` | VARCHAR | no | indexed |
| `entity_type` | VARCHAR | yes | indexed |
| `entity_id` | VARCHAR | yes | indexed |
| `details` | JSON | no |  |
| `ip` | VARCHAR | yes |  |
| `request_id` | VARCHAR | yes |  |
| `created_at` | DATETIME | no | indexed |

**`workspaces`**: Tenant boundary. Every other table carries a workspace_id; settings JSON holds AI provider, theme and retention.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `name` | VARCHAR | no |  |
| `slug` | VARCHAR | no | unique |
| `is_demo` | BOOLEAN | no |  |
| `settings` | JSON | no |  |
| `created_at` | DATETIME | no |  |

**`ai_generations`**: TARA metric-generator suggestions with mode (ai/offline), validity, acceptance and latency.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `user_id` | VARCHAR | yes |  |
| `prompt` | TEXT | no |  |
| `dataset_id` | VARCHAR | yes |  |
| `mode` | VARCHAR | no |  |
| `provider` | VARCHAR | yes |  |
| `latency_ms` | FLOAT | no |  |
| `output` | JSON | no |  |
| `valid` | BOOLEAN | no |  |
| `status` | VARCHAR | no |  |
| `metric_id` | VARCHAR | yes |  |
| `accepted` | BOOLEAN | no |  |
| `error` | TEXT | yes |  |
| `created_at` | DATETIME | no |  |

**`connections`**: External PostgreSQL/MySQL connections; the password is Fernet-encrypted at rest.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `name` | VARCHAR | no |  |
| `kind` | VARCHAR | no |  |
| `host` | VARCHAR | no |  |
| `port` | INTEGER | no |  |
| `database` | VARCHAR | no |  |
| `username` | VARCHAR | no |  |
| `password_enc` | TEXT | no |  |
| `options` | JSON | no |  |
| `last_status` | VARCHAR | yes |  |
| `last_error` | TEXT | yes |  |
| `last_tested_at` | DATETIME | yes |  |
| `created_by` | VARCHAR | yes |  |
| `created_at` | DATETIME | no |  |

**`dashboards`**: Saved dashboards: widget layout JSON, filters and the version policy (latest_published or pinned).

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `name` | VARCHAR | no |  |
| `description` | TEXT | yes |  |
| `widgets` | JSON | no |  |
| `filters` | JSON | no |  |
| `version_policy` | VARCHAR | no |  |
| `template` | VARCHAR | yes |  |
| `created_by` | VARCHAR | yes |  |
| `created_at` | DATETIME | no |  |
| `updated_at` | DATETIME | no |  |

**`evaluation_runs`**: Stored results of each performance evaluation run.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `user_id` | VARCHAR | yes |  |
| `results` | JSON | no |  |
| `duration_ms` | FLOAT | no |  |
| `created_at` | DATETIME | no |  |

**`executions`**: History of validations and executions (Formula Lab, Ask TARA, dashboards) with duration, scanned rows and error.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `user_id` | VARCHAR | yes |  |
| `dataset_id` | VARCHAR | yes |  |
| `kind` | VARCHAR | no |  |
| `expression` | TEXT | yes |  |
| `ok` | BOOLEAN | no |  |
| `duration_ms` | FLOAT | no |  |
| `scanned_rows` | BIGINT | no |  |
| `row_count` | BIGINT | no |  |
| `error` | TEXT | yes |  |
| `sql_text` | TEXT | yes |  |
| `created_at` | DATETIME | no | indexed |

**`notifications`**: In-app notifications per workspace or user with per-user read state.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `user_id` | VARCHAR | yes | indexed |
| `title` | VARCHAR | no |  |
| `body` | TEXT | yes |  |
| `kind` | VARCHAR | no |  |
| `link` | VARCHAR | yes |  |
| `read_by` | JSON | no |  |
| `created_at` | DATETIME | no | indexed |

**`users`**: Accounts with an Argon2 password hash, a role (admin, data_analyst, business_user, reviewer) and a workspace.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `email` | VARCHAR | no | unique |
| `name` | VARCHAR | no |  |
| `password_hash` | VARCHAR | no |  |
| `role` | VARCHAR | no |  |
| `is_active` | BOOLEAN | no |  |
| `is_demo` | BOOLEAN | no |  |
| `avatar_url` | VARCHAR | yes |  |
| `title` | VARCHAR | yes |  |
| `created_at` | DATETIME | no |  |
| `last_login` | DATETIME | yes |  |

**`chat_conversations`**: Ask TARA conversations per user.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `user_id` | VARCHAR | no | FK -> users.id, indexed |
| `title` | VARCHAR | no |  |
| `created_at` | DATETIME | no |  |
| `updated_at` | DATETIME | no |  |

**`datasets`**: Dataset catalog: format, status/progress, detected schema, column profile and the Parquet path produced by ingestion.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `name` | VARCHAR | no |  |
| `description` | TEXT | yes |  |
| `source_type` | VARCHAR | no |  |
| `file_format` | VARCHAR | yes |  |
| `original_filename` | VARCHAR | yes |  |
| `raw_path` | VARCHAR | yes |  |
| `parquet_path` | VARCHAR | yes |  |
| `size_bytes` | BIGINT | no |  |
| `row_count` | BIGINT | no |  |
| `column_count` | INTEGER | no |  |
| `status` | VARCHAR | no |  |
| `progress` | INTEGER | no |  |
| `stage` | VARCHAR | yes |  |
| `error` | TEXT | yes |  |
| `schema_json` | JSON | no |  |
| `profile` | JSON | no |  |
| `date_column` | VARCHAR | yes |  |
| `connection_id` | VARCHAR | yes | FK -> connections.id |
| `source_table` | VARCHAR | yes |  |
| `is_demo` | BOOLEAN | no |  |
| `created_by` | VARCHAR | yes |  |
| `created_at` | DATETIME | no |  |
| `updated_at` | DATETIME | no |  |

**`password_resets`**: Single-use, hashed, one-hour password reset tokens.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `user_id` | VARCHAR | no | FK -> users.id, indexed |
| `token_hash` | VARCHAR | no | unique |
| `expires_at` | DATETIME | no |  |
| `used` | BOOLEAN | no |  |
| `created_at` | DATETIME | no |  |

**`refresh_tokens`**: Hashed, rotating refresh tokens (httpOnly cookie) with expiry and revocation flag.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `user_id` | VARCHAR | no | FK -> users.id, indexed |
| `token_hash` | VARCHAR | no | unique |
| `expires_at` | DATETIME | no |  |
| `revoked` | BOOLEAN | no |  |
| `created_at` | DATETIME | no |  |

**`chat_messages`**: Messages with the structured answer payload (table, chart, sources, applied filters).

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `conversation_id` | VARCHAR | no | FK -> chat_conversations.id, indexed |
| `role` | VARCHAR | no |  |
| `content` | TEXT | no |  |
| `payload` | JSON | no |  |
| `created_at` | DATETIME | no |  |

**`ingestion_jobs`**: One row per background ingestion run: stage, progress, duration, runner and error report.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `dataset_id` | VARCHAR | no | FK -> datasets.id, indexed |
| `status` | VARCHAR | no |  |
| `stage` | VARCHAR | yes |  |
| `progress` | INTEGER | no |  |
| `rows` | INTEGER | no |  |
| `bytes` | BIGINT | no |  |
| `duration_ms` | INTEGER | yes |  |
| `error_report` | JSON | no |  |
| `runner` | VARCHAR | yes |  |
| `created_at` | DATETIME | no |  |
| `finished_at` | DATETIME | yes |  |

**`metrics`**: Governed metric definitions (working copy). A partial unique index allows only one live definition per workspace and key.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `key` | VARCHAR | no | indexed |
| `name` | VARCHAR | no |  |
| `description` | TEXT | yes |  |
| `business_definition` | TEXT | yes |  |
| `formula` | TEXT | no |  |
| `filters` | TEXT | yes |  |
| `aggregation` | VARCHAR | yes |  |
| `unit` | VARCHAR | yes |  |
| `time_window` | VARCHAR | no |  |
| `date_column` | VARCHAR | yes |  |
| `dataset_id` | VARCHAR | yes | FK -> datasets.id |
| `department` | VARCHAR | yes |  |
| `category` | VARCHAR | yes |  |
| `owner_id` | VARCHAR | yes | FK -> users.id |
| `status` | VARCHAR | no |  |
| `version` | INTEGER | no |  |
| `published_version` | INTEGER | yes |  |
| `is_live` | BOOLEAN | no |  |
| `depends_on` | JSON | no |  |
| `source` | VARCHAR | no |  |
| `created_at` | DATETIME | no |  |
| `updated_at` | DATETIME | no |  |

Unique index `uq_metric_live_key` on (workspace_id, key) WHERE is_live IS TRUE (partial)

**`conflicts`**: Detected definition conflicts with differences, severity, recommendation, affected objects and workflow status.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `metric_key` | VARCHAR | no | indexed |
| `metric_a_id` | VARCHAR | no | FK -> metrics.id |
| `metric_b_id` | VARCHAR | no | FK -> metrics.id |
| `conflict_type` | VARCHAR | no |  |
| `severity` | VARCHAR | no |  |
| `differences` | JSON | no |  |
| `explanation` | TEXT | no |  |
| `recommendation` | TEXT | no |  |
| `recommended_action` | VARCHAR | yes |  |
| `affected` | JSON | no |  |
| `fingerprint` | VARCHAR | no |  |
| `status` | VARCHAR | no |  |
| `assignee_id` | VARCHAR | yes | FK -> users.id |
| `resolution_action` | VARCHAR | yes |  |
| `resolution_note` | TEXT | yes |  |
| `detected_at` | DATETIME | no |  |
| `resolved_at` | DATETIME | yes |  |

**`metric_reviews`**: Append-only approval workflow events: submit, approve, reject, publish, deprecate.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `metric_id` | VARCHAR | no | FK -> metrics.id, indexed |
| `version` | INTEGER | no |  |
| `user_id` | VARCHAR | yes | FK -> users.id |
| `decision` | VARCHAR | no |  |
| `comment` | TEXT | yes |  |
| `created_at` | DATETIME | no |  |

**`metric_versions`**: Immutable version snapshots. UPDATE/DELETE are blocked by an ORM guard and a database trigger.

| Column | Type | Null | Key / constraint |
|---|---|:-:|---|
| `id` | VARCHAR | no | PK |
| `workspace_id` | VARCHAR | no | FK -> workspaces.id, indexed |
| `metric_id` | VARCHAR | no | FK -> metrics.id, indexed |
| `number` | INTEGER | no |  |
| `snapshot` | JSON | no |  |
| `change_summary` | VARCHAR | no |  |
| `reason` | TEXT | yes |  |
| `author_id` | VARCHAR | yes | FK -> users.id |
| `rollback_of` | INTEGER | yes |  |
| `created_at` | DATETIME | no |  |
