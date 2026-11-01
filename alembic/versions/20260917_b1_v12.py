"""Versiona la exclusión exploratoria sin reinterpretar evaluaciones anteriores."""
from alembic import op
import sqlalchemy as sa

revision = "20260917_b1_v12"
down_revision = "20260917_votacion_cohortes"
branch_labels = depends_on = None


def upgrade():
    conn = op.get_bind()
    anterior = conn.execute(sa.text("SELECT id FROM versiones_protocolo WHERE codigo='B-1' AND version='1.1'")).scalar_one()
    nuevo = conn.execute(sa.text("""INSERT INTO versiones_protocolo
        (codigo, version, nombre, tipo_objeto, descripcion, activo, creado_en, model_policy, matriz_lentes)
        SELECT codigo, '1.2', nombre, tipo_objeto,
            descripcion || ' Los resultados exploratorios no alimentan controles ni evidencia institucional.',
            true, CURRENT_TIMESTAMP,
            model_policy || jsonb_build_object('excluir_resultados_exploratorios', true), matriz_lentes
        FROM versiones_protocolo WHERE id=:anterior RETURNING id"""), {"anterior": anterior}).scalar_one()
    conn.execute(sa.text("""INSERT INTO definiciones_control
        (protocolo_id,codigo,nombre,descripcion,lente,obligatorio,criticidad,condicion_aplicabilidad,evidencia_requerida,orden)
        SELECT :nuevo,codigo,nombre,descripcion,lente,obligatorio,criticidad,condicion_aplicabilidad,evidencia_requerida,orden
        FROM definiciones_control WHERE protocolo_id=:anterior"""), {"nuevo": nuevo, "anterior": anterior})
    conn.execute(sa.text("UPDATE versiones_protocolo SET activo=false WHERE codigo='B-1' AND id<>:nuevo"), {"nuevo": nuevo})


def downgrade():
    conn = op.get_bind()
    nuevo = conn.execute(sa.text("SELECT id FROM versiones_protocolo WHERE codigo='B-1' AND version='1.2'")).scalar_one()
    if conn.execute(sa.text("SELECT count(*) FROM evaluaciones_certificacion WHERE protocolo_id=:id"), {"id": nuevo}).scalar():
        raise RuntimeError("B-1 1.2 ya tiene evaluaciones: no eliminar su versión histórica")
    conn.execute(sa.text("DELETE FROM definiciones_control WHERE protocolo_id=:id"), {"id": nuevo})
    conn.execute(sa.text("DELETE FROM versiones_protocolo WHERE id=:id"), {"id": nuevo})
    conn.execute(sa.text("UPDATE versiones_protocolo SET activo=true WHERE codigo='B-1' AND version='1.1'"))
