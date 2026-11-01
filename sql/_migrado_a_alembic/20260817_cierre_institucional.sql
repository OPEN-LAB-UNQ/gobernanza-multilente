-- 2026-08-17 - Cierre institucional Gobernanza Multilente
-- Migracion idempotente: hallazgos estructurados, devolucion con cobertura,
-- decision humana no binaria y seleccion de hallazgos para escalamiento.

ALTER TABLE hallazgos ADD COLUMN IF NOT EXISTS tipo_evidencia VARCHAR(60);
ALTER TABLE hallazgos ADD COLUMN IF NOT EXISTS alcance VARCHAR(60) DEFAULT 'agregado';
ALTER TABLE hallazgos ADD COLUMN IF NOT EXISTS metodo VARCHAR(120);
ALTER TABLE hallazgos ADD COLUMN IF NOT EXISTS incertidumbre VARCHAR(20) DEFAULT 'media';
ALTER TABLE hallazgos ADD COLUMN IF NOT EXISTS estado_validacion VARCHAR(60) DEFAULT 'pendiente_decision_humana';
ALTER TABLE hallazgos ADD COLUMN IF NOT EXISTS pregunta_institucional TEXT;
ALTER TABLE hallazgos ADD COLUMN IF NOT EXISTS limites JSONB;

ALTER TABLE devoluciones ADD COLUMN IF NOT EXISTS estado VARCHAR(50) DEFAULT 'PENDIENTE';
ALTER TABLE devoluciones ADD COLUMN IF NOT EXISTS cobertura JSONB;

ALTER TABLE decisiones_director ADD COLUMN IF NOT EXISTS tipo_decision VARCHAR(40) DEFAULT 'sin_escalamiento';
ALTER TABLE decisiones_director ADD COLUMN IF NOT EXISTS pregunta_institucional TEXT;
ALTER TABLE decisiones_director ADD COLUMN IF NOT EXISTS hallazgo_ids JSONB;

UPDATE hallazgos
SET alcance = COALESCE(alcance, 'agregado'),
    incertidumbre = COALESCE(incertidumbre, 'media'),
    estado_validacion = COALESCE(estado_validacion, 'pendiente_decision_humana');

UPDATE devoluciones
SET estado = CASE WHEN hay_hallazgos THEN 'CON_SENALES_COMUNICABLES' ELSE 'SIN_SENALES_COMUNICABLES' END
WHERE estado IS NULL OR estado = 'PENDIENTE';

UPDATE decisiones_director
SET tipo_decision = CASE WHEN escalar THEN 'escalar_formalmente' ELSE 'sin_escalamiento' END
WHERE tipo_decision IS NULL OR tipo_decision = 'sin_escalamiento';
