ALTER TABLE triangulaciones ADD COLUMN IF NOT EXISTS convergencia_multilente JSONB NOT NULL DEFAULT '[]'::jsonb;
