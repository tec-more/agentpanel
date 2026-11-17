-- ContentOps 素材资产表（M1 素材存储 + M2/M3 OCR/ASR 缓存）
-- openGauss 兼容：IF NOT EXISTS，禁用 to_regclass / ON CONFLICT
CREATE TABLE IF NOT EXISTS contentops_media_asset (
    id BIGSERIAL PRIMARY KEY,
    content_id BIGINT,
    kind VARCHAR(16) NOT NULL DEFAULT 'image',
    filename VARCHAR(255) NOT NULL,
    rel_path VARCHAR(512) NOT NULL,
    url VARCHAR(512) NOT NULL,
    content_type VARCHAR(64) NOT NULL,
    size_bytes BIGINT NOT NULL DEFAULT 0,
    width INT,
    height INT,
    duration_sec DOUBLE PRECISION,
    tags JSONB NOT NULL DEFAULT '[]',
    ocr_text TEXT,
    ocr_status VARCHAR(16) NOT NULL DEFAULT 'pending',
    extra JSONB NOT NULL DEFAULT '{}',
    owner_type VARCHAR(3) NOT NULL DEFAULT 'usr',
    owner_id BIGINT,
    uploader_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_media_owner ON contentops_media_asset (owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_cops_media_content ON contentops_media_asset (content_id, kind);
CREATE INDEX IF NOT EXISTS idx_cops_media_ocr ON contentops_media_asset (kind, ocr_status);
