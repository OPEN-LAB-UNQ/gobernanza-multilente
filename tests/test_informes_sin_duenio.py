"""Un informe sin dueño sólo lo ve un admin (antes lo veía cualquier usuario)."""
from types import SimpleNamespace as NS

from routers.certificaciones import _puede_ver_objeto
from routers.decisiones import _puede_decidir as puede_ver_decision
from routers.exploratorio import _puede_ver_informe
from routers.informes import _puede_ver

CHEQUEOS = (_puede_ver, _puede_ver_informe, _puede_ver_objeto, puede_ver_decision)


def test_informe_sin_duenio_solo_admin():
    huerfano = NS(usuario_id=None)
    for chequeo in CHEQUEOS:
        assert chequeo(NS(rol="admin", id=1), huerfano)
        assert not chequeo(NS(rol="analista", id=7), huerfano)
        assert not chequeo(NS(rol="lector", id=8), huerfano)


def test_duenio_sigue_viendo_lo_suyo_y_no_lo_ajeno():
    for chequeo in CHEQUEOS:
        assert chequeo(NS(rol="analista", id=7), NS(usuario_id=7))
        assert not chequeo(NS(rol="analista", id=7), NS(usuario_id=9))
