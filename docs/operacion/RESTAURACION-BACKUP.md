# Prueba de restauración del backup

Última prueba: 29/09/2026, con `backups/db/gobernanza-20260929-044733.dump`.

    D=$(ls -t /home/gobernanza/backups/db/gobernanza-2026*.dump | head -1)
    sudo -u postgres createdb gob_prueba_restauracion
    cat "$D" | sudo -u postgres pg_restore -d gob_prueba_restauracion --no-owner --no-privileges
    sudo -u postgres psql -d gob_prueba_restauracion -tAc "select count(*) from informes"
    sudo -u postgres dropdb gob_prueba_restauracion

El dump es legible sólo por root: se pasa a `pg_restore` por la entrada estándar. El único
aviso esperado es `unrecognized configuration parameter "transaction_timeout"` (el `pg_dump`
es más nuevo que el servidor); no afecta los datos.

Resultado del 29/09: restauración completa; conteos coherentes con la base viva al momento de
la prueba (116 informes en el dump contra 115 vivos por un borrado posterior; 51 proyectos, 92
usuarios; las 29 devoluciones docentes del 28/09 presentes).

Pendiente: una copia fuera de este servidor. Hoy los dumps viven sólo en este disco.

## Versión de las herramientas (verificado el 02/10/2026)

El servidor de base es PostgreSQL 15.19, pero el `pg_dump` que usa el script es el 18.6
(formato de archivo 1.16). Para restaurar en otro servidor hace falta `pg_restore` 18 o
posterior: el `pg_restore` 15 no lee ese formato. Instalar el cliente de PostgreSQL 18 en el
destino (paquete `postgresql18`), aunque la base de destino sea 15.

## Dumps manuales

Los dumps tomados a mano antes de un borrado se nombran `manual-gobernanza-…dump`: así no
entran en la retención de 14 días del script (que borra `gobernanza-*.dump`) y se conservan.
