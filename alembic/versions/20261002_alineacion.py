"""Alinea la base con models.py: NOT NULL en fechas (0 nulos al 02/10/2026) e índices.

No modifica datos. Los índices cubren las claves foráneas más consultadas (hallazgos e
interpretaciones por informe, informes por usuario y área) y el índice que el modelo ya
declaraba en registros_monitoreo.creado_en.
"""
from alembic import op

revision = "20261002_alineacion"
down_revision = "20260929_sesiones"
branch_labels = depends_on = None

NOT_NULL = [('areas', 'creado_en'), ('usuarios', 'creado_en'), ('informes', 'creado_en'), ('proyectos_ia', 'creado_en'), ('proyectos_ia', 'actualizado_en'), ('activity_events', 'creado_en'), ('analysis_jobs', 'creado_en'), ('devoluciones', 'creado_en'), ('hallazgos', 'creado_en'), ('interpretaciones_modelo', 'creado_en'), ('learning_events', 'creado_en'), ('learning_events_incubadora', 'creado_en'), ('mensajes_proyecto_ia', 'creado_en'), ('registros_monitoreo', 'creado_en'), ('triangulaciones', 'creado_en'), ('votos_proyecto_ia', 'creado_en'), ('votos_proyecto_ia', 'actualizado_en'), ('votos_segunda_vuelta', 'creado_en'), ('votos_segunda_vuelta', 'actualizado_en'), ('decisiones_director', 'decidido_en'), ('documentos_enrutamiento', 'creado_en')]
INDICES = [('registros_monitoreo', 'creado_en'), ('hallazgos', 'informe_id'), ('interpretaciones_modelo', 'informe_id'), ('informes', 'usuario_id'), ('informes', 'area_id'), ('resultados_control', 'revisado_por_id'), ('evidencias_control', 'agregado_por_id')]


def upgrade():
    for tabla, columna in NOT_NULL:
        op.alter_column(tabla, columna, nullable=False)
    for tabla, columna in INDICES:
        op.create_index(f"ix_{tabla}_{columna}", tabla, [columna], if_not_exists=True)


def downgrade():
    for tabla, columna in INDICES:
        if (tabla, columna) != ("registros_monitoreo", "creado_en"):
            op.drop_index(f"ix_{tabla}_{columna}", table_name=tabla)
    for tabla, columna in NOT_NULL:
        op.alter_column(tabla, columna, nullable=True)
