-- taskiq-beat 调度表（幂等建表，core_ 前缀 => 恒执行，不依赖插件启用态）
-- 字段/索引/类型逐字段对照 taskiq-beat 1.4.0 的 taskiq_beat/models.py（2026-11-14 解包核对）。
-- 注意：SQL 迁移在 generate_schemas 之前执行；CREATE TABLE IF NOT EXISTS 保证不冲突。
-- JSON 列用 JSONB 以与项目 event_subscriptions 约定一致（R16 需验证 SQLAlchemy JSON 类型对 JSONB 列读写兼容）。

CREATE TABLE IF NOT EXISTS scheduler_job (
    id                   VARCHAR(36)  PRIMARY KEY,
    name                 VARCHAR(255),
    description          TEXT,
    task_name            VARCHAR(255) NOT NULL,
    kind                 VARCHAR(16)  NOT NULL,
    strategy             VARCHAR(16)  NOT NULL,
    trigger_payload      JSONB        NOT NULL,
    task_args            JSONB        NOT NULL,
    task_kwargs          JSONB        NOT NULL,
    metadata_payload     JSONB        NOT NULL,
    is_enabled           BOOLEAN      NOT NULL,
    next_run_at          TIMESTAMPTZ,
    claimed_by           VARCHAR(128),
    claimed_at           TIMESTAMPTZ,
    claim_expires_at     TIMESTAMPTZ,
    last_run_at          TIMESTAMPTZ,
    last_error           TEXT,
    last_dispatched_task_id VARCHAR(255),
    dispatch_count       INTEGER      NOT NULL,
    created_at           TIMESTAMPTZ  NOT NULL,
    updated_at           TIMESTAMPTZ  NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduler_run (
    id                VARCHAR(36)  PRIMARY KEY,
    job_id            VARCHAR(36)  NOT NULL REFERENCES scheduler_job(id) ON DELETE CASCADE,
    status            VARCHAR(16)  NOT NULL,
    scheduled_for     TIMESTAMPTZ  NOT NULL,
    dispatched_at     TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    broker_task_id    VARCHAR(255),
    error             TEXT,
    created_at        TIMESTAMPTZ  NOT NULL,
    updated_at        TIMESTAMPTZ  NOT NULL
);

-- 复合索引（taskiq-beat 查询依赖，名称须与 SchedulerBase.__table_args__ 完全一致）
CREATE INDEX IF NOT EXISTS ix_scheduler_job_ready_lookup   ON scheduler_job (is_enabled, next_run_at, claim_expires_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_claim_owner    ON scheduler_job (claimed_by, claim_expires_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_job_finished    ON scheduler_run (job_id, finished_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_status_finished ON scheduler_run (status, finished_at);

-- 单列索引（对应模型 index=True；命名与 create_all 自动生成一致，避免 dev/prod 漂移）
CREATE INDEX IF NOT EXISTS ix_scheduler_job_task_name        ON scheduler_job (task_name);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_is_enabled       ON scheduler_job (is_enabled);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_next_run_at      ON scheduler_job (next_run_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_claimed_by       ON scheduler_job (claimed_by);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_claim_expires_at ON scheduler_job (claim_expires_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_updated_at      ON scheduler_job (updated_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_job_id           ON scheduler_run (job_id);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_status           ON scheduler_run (status);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_scheduled_for    ON scheduler_run (scheduled_for);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_broker_task_id  ON scheduler_run (broker_task_id);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_finished_at     ON scheduler_run (finished_at);
