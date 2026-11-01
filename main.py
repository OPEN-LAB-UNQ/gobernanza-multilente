import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from core.auth import get_current_user, require_password_middleware, seed_initial_admin
from routers import (
    aprendizajes,
    aprendizajes_incubadora,
    areas,
    auth,
    biblioteca_casos,
    calibraciones,
    carga_rapida,
    certificaciones,
    decisiones,
    ejemplos,
    exploratorio,
    informes,
    jobs,
    monitoreo,
    ocr,
    proyectos_ia,
    sistema,
    sugerencias,
    votos_proyectos_ia,
)
from services import grupos, uso_publico
from versiones import ANALYSIS_VERSION, API_VERSION, APP_VERSION, DOCUMENT_VERSION, version_codigo


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from services import jobs as jobs_svc

    seed_initial_admin()
    jobs_svc.recover_processing_jobs()
    jobs_svc.ensure_worker_started()
    yield


app = FastAPI(
    title="Gobernanza Multilente",
    description=(
        "Segunda lectura de información agregada asistida por IA: lentes "
        "analíticas, triangulación, trazabilidad y revisión humana. No es "
        "una herramienta de auditoría ni de atribución de responsabilidades, "
        "ni evalúa ideologías, partidos o decisiones de oportunidad institucional."
    ),
    version=API_VERSION,
    lifespan=lifespan,
)

app.middleware("http")(require_password_middleware)


app.include_router(auth.router)

api = APIRouter(prefix="/api")
api.include_router(areas.router)
api.include_router(informes.router)
api.include_router(jobs.router)
api.include_router(ejemplos.router)
api.include_router(decisiones.router)
api.include_router(carga_rapida.router)
api.include_router(calibraciones.router)
api.include_router(biblioteca_casos.router)
api.include_router(certificaciones.router)
api.include_router(proyectos_ia.router)
api.include_router(votos_proyectos_ia.router)
api.include_router(exploratorio.router)
api.include_router(sugerencias.router)
api.include_router(ocr.router)
app.include_router(api)

app.include_router(sistema.router)
app.include_router(aprendizajes.router)
app.include_router(aprendizajes_incubadora.router)
app.include_router(monitoreo.router)
app.include_router(certificaciones.verification_router)

STATIC_DIR = Path(__file__).parent / "static"
SITE_URL = "https://gobernanza.entornodepruebas.com.ar"
PUBLIC_EVIDENCE = STATIC_DIR / "public-evidence.json"

LANDING_NAV = """<a href=\"#criterio\">Criterio de uso</a><a href=\"#preguntas\">Preguntas frecuentes</a><a href=\"#ejemplos\">Ejemplos</a>
        <a href=\"#prueba-institucional\">Ponerlo a prueba</a>
        <a href=\"/detalle\">Ficha técnica</a>"""
DETAIL_NAV = """<a href=\"/presentacion\">← Presentación ejecutiva</a>
        <a href=\"#alcance\">Qué es</a><a href=\"#metodologia\">Cómo trabaja</a>
        <a href=\"#procesamiento\">Datos y privacidad</a><a href=\"#constancia\">Qué entrega</a>
        <a href=\"#validacion\">Evidencia y límites</a><a href=\"#prueba-detalle\">Validación</a>"""
# La charla no suma entradas al menú de /presentacion: sólo enlaza hacia afuera.
CHARLA_NAV = """<a href=\"/presentacion\">Conocer Gobernanza Multilente</a>"""
PRIVACIDAD_NAV = """<a href=\"/presentacion\">← Presentación ejecutiva</a>
        <a href=\"#datos\">Datos</a><a href=\"#cookies\">Cookies</a><a href=\"#proveedores\">Proveedores</a>
        <a href=\"#derechos\">Derechos</a><a href=\"#aviso-legal\">Aviso legal</a>"""


def _pagina_institucional(*, detalle: bool = False, charla: bool = False, privacidad: bool = False) -> HTMLResponse:
    if detalle:
        titulo = "Ficha técnica · Gobernanza Multilente"
        descripcion = (
            "Ficha de Gobernanza Multilente: qué comprueba, qué interpreta, qué no puede evaluar, "
            "cómo trata los datos, qué entrega y qué falta demostrar."
        )
        canonical = f"{SITE_URL}/detalle"
    elif charla:
        titulo = "Gobernanza Multilente · Una segunda lectura antes de decidir (charla)"
        descripcion = (
            "Charla relámpago en el Encuentro Nacional de Tecnología Cívica, Guadalajara, 15 de octubre de 2026: "
            "cómo una segunda lectura de los informes puede ayudar a quien decide a encontrar puntos ciegos."
        )
        canonical = f"{SITE_URL}/multilente"
    elif privacidad:
        titulo = "Privacidad, cookies y aviso legal · Gobernanza Multilente"
        descripcion = (
            "Qué datos personales trata Gobernanza Multilente, con qué base legal y por cuánto tiempo: cookies, "
            "proveedores, transferencias, derechos y aviso legal (Ley 25.326 y RGPD)."
        )
        canonical = f"{SITE_URL}/privacidad"
    else:
        titulo = "Gobernanza Multilente · Una segunda lectura antes de decidir"
        descripcion = (
            "Gobernanza Multilente lleva los principios de gobernanza a algo que se puede comprobar: "
            "una segunda lectura de informes con datos agregados antes de decidir. "
            "Registra evidencia y límites; la decisión sigue siendo humana."
        )
        canonical = f"{SITE_URL}/presentacion"
    html = (STATIC_DIR / "presentacion.html").read_text(encoding="utf-8")
    if detalle or charla or privacidad:
        before, marker, remainder = html.partition("  <main>")
        if not marker or "  </main>" not in remainder:
            raise RuntimeError("No se encontró el cuerpo de la presentación")
        after = remainder.rsplit("  </main>", 1)[1]
        cuerpo = "detalle-body.html" if detalle else "privacidad-body.html" if privacidad else "multilente-body.html"
        body = (STATIC_DIR / cuerpo).read_text(encoding="utf-8")
        html = before + "  <main>\n" + body + "\n  </main>" + after
    evidence = json.loads(PUBLIC_EVIDENCE.read_text(encoding="utf-8"))
    tests = evidence["tests"]
    summary = f'{tests["passed"]} / {tests["collected"]}'
    html = (
        html.replace("__PAGE_TITLE__", titulo)
        .replace("__PAGE_DESCRIPTION__", descripcion)
        .replace("__PAGE_CANONICAL__", canonical)
        .replace("__PAGE_NAV__", DETAIL_NAV if detalle else CHARLA_NAV if charla
                 else PRIVACIDAD_NAV if privacidad else LANDING_NAV)
        .replace("__TEST_SUMMARY__", summary)
        .replace("__TEST_DATE__", tests["date"])
        .replace("__TEST_COLLECTED__", str(tests["collected"]))
        .replace("__TEST_PASSED__", str(tests["passed"]))
        .replace("__TEST_FAILED__", str(tests["failed"]))
        .replace("__TEST_SKIPPED__", str(tests["skipped"]))
        .replace("__TEST_XFAILED__", str(tests["xfailed"]))
        .replace("__TEST_CODE_VERSION__", str(evidence.get("code_fingerprint") or "no registrada")[:12])
        .replace("__APP_VERSION__", APP_VERSION)
        .replace("__MOTOR_VERSION__", ANALYSIS_VERSION)
        .replace("__DOCUMENT_VERSION__", DOCUMENT_VERSION)
        .replace("__CODE_VERSION__", version_codigo()[:12])
    )
    uso = uso_publico.vigente(respaldo=evidence.get("uso"))
    for clave in ("informes", "informes_con_devolucion", "participantes", "observaciones", "informes_sin_senales", "proyectos",
                  "proyectos_entregados", "desde", "hasta", "fecha"):
        html = html.replace(f"__USO_{clave.upper()}__", str(uso.get(clave, "—")))
    return HTMLResponse(html, headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/presentacion", include_in_schema=False)
def presentacion_institucional():
    return _pagina_institucional(detalle=False)


@app.get("/detalle", include_in_schema=False)
def detalle_institucional():
    return _pagina_institucional(detalle=True)


@app.get("/multilente", include_in_schema=False)
def charla_multilente():
    return _pagina_institucional(charla=True)


@app.get("/privacidad", include_in_schema=False)
def privacidad_cookies_aviso_legal():
    return _pagina_institucional(privacidad=True)


@app.get("/robots.txt", include_in_schema=False)
def robots_txt():
    # Solo la presentación y la ficha son públicas; el resto de la aplicación pide ingreso.
    texto = (
        "User-agent: *\nAllow: /presentacion\nAllow: /detalle\nAllow: /multilente\nAllow: /privacidad\nDisallow: /\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )
    return Response(texto, media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml():
    urls = "".join(f"<url><loc>{SITE_URL}{ruta}</loc></url>" for ruta in ("/presentacion", "/detalle", "/multilente", "/privacidad"))
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return Response(xml, media_type="application/xml")


# 0.10.62: index.html tiene tramos escritos a mano sobre proyectos de las comisiones originales (las tres síntesis y
# el piloto de Monitoreo). A una cuenta de otro grupo no se le entregan; a las demás, el aviso que los reemplaza.
INDEX_PATH = STATIC_DIR / "index.html"
_TRAMOS = {
    "por_defecto": re.compile(r"<!-- solo-grupo-por-defecto -->.*?<!-- /solo-grupo-por-defecto -->", re.S),
    "otro_grupo": re.compile(r"<!-- solo-otro-grupo -->.*?<!-- /solo-otro-grupo -->", re.S),
}


def index_para(usuario) -> str:
    otro_grupo = not grupos.ve_todo(usuario) and grupos.de(usuario) is not None
    return _TRAMOS["por_defecto" if otro_grupo else "otro_grupo"].sub("", INDEX_PATH.read_text(encoding="utf-8"))


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def aplicacion(usuario=Depends(get_current_user)):
    return HTMLResponse(index_para(usuario), headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"})


class NoCacheStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response


app.mount("/", NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="static")
