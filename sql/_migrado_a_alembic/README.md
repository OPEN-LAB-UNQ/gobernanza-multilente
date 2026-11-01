Estos .sql ya fueron aplicados (corrian a mano en cada arranque via
`_ensure_runtime_schema()`, retirado). El esquema resultante quedo capturado
como baseline en `alembic/versions/90bee6470721_baseline_esquema_existente.py`.
De aca en mas, cambios de esquema van por `alembic revision --autogenerate`.
Se conservan estos archivos solo como historial, no se ejecutan mas.
