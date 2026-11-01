"""0.10.58: la aplicación queda prolija para la Unión Europea (RGPD y directiva de privacidad electrónica).

Una sola cookie, estrictamente necesaria y sólo con sesión; preferencias en el navegador que elige la persona; sin
analítica ni recursos de terceros al abrir una página; el video de YouTube detrás de un botón; y una página
/privacidad con responsable, datos, bases legales, conservación, cookies, proveedores, transferencias, derechos y
aviso legal, enlazada desde cada página pública. Si se agrega una cookie o una clave de almacenamiento del
navegador, estas pruebas obligan a declararla en /privacidad.
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from core.auth import COOKIE_NAME, login_html
from main import app

RAIZ = Path(__file__).resolve().parent.parent
STATIC = RAIZ / "static"
PUBLICAS = ("/presentacion", "/detalle", "/multilente", "/privacidad")
# Un recurso que el navegador baja solo al abrir la página (no un enlace) desde otro dominio.
TERCERO = re.compile(r'<(?:script|link|img|iframe|source|video|audio|embed|object)\b[^>]*\b(?:src|href)="(?:https?:)?//'
                     r'(?!gobernanza\.entornodepruebas\.com\.ar)', re.I)
client = TestClient(app)


def _pagina(ruta):
    r = client.get(ruta)
    assert r.status_code == 200, ruta
    return r.text


def test_privacidad_es_publica_y_completa():
    html = _pagina("/privacidad")
    assert "<title>Privacidad, cookies y aviso legal · Gobernanza Multilente</title>" in html
    assert 'rel="canonical" href="https://gobernanza.entornodepruebas.com.ar/privacidad"' in html
    assert "__PAGE_" not in html and "__APP_VERSION__" not in html
    for texto in ("Ley 25.326", "Reglamento General de Protección de Datos", "Maximiliano Pérez",
                  "maximilianoperez1981@gmail.com", "art. 6.1.f", "art. 6.1.b", "10 días", "14 días", "24 meses",
                  "Decisión 2003/490/CE", "12 horas", "OpenAI", "Gemini", "DeepSeek", "no envía nada",
                  "el archivo original no se guarda", "autoridad de protección de datos",
                  "Agencia Española de Protección de Datos", "Aviso legal", "Última actualización"):
        assert texto in html, texto
    for ancla in ("responsable", "datos", "cookies", "proveedores", "derechos", "seguridad", "aviso-legal", "cambios"):
        assert f'id="{ancla}"' in html and f'href="#{ancla}"' in html
    # Como en la presentación, el correo se publica como texto y no como enlace.
    assert 'href="mailto:' not in html
    assert "Uso educativo y de investigación" not in html  # frase retirada de las páginas públicas


def test_paginas_publicas_no_cargan_recursos_de_terceros():
    probar = (STATIC / "probar.html").read_text(encoding="utf-8")
    for nombre, html in [(r, _pagina(r)) for r in PUBLICAS] + [("login", login_html()), ("probar", probar)]:
        assert not TERCERO.search(html), (nombre, TERCERO.search(html).group(0))
        for rastro in ("fonts.googleapis", "fonts.gstatic", "googletagmanager", "google-analytics", "gtag(",
                       "facebook.net", "hotjar", "clarity.ms", "@import url(http"):
            assert rastro not in html, (nombre, rastro)


def test_video_detras_de_un_boton():
    html = _pagina("/presentacion")
    assert "<iframe" not in html  # nada se conecta con YouTube al abrir la página
    assert 'class="video-play" data-yt="iWddq1wAOrY"' in html
    assert '<script src="/presentacion-video.js" defer></script>' in html
    assert client.get("/presentacion-video.js").status_code == 200  # público: se abre sin sesión
    js = (STATIC / "presentacion-video.js").read_text(encoding="utf-8")
    assert "https://www.youtube-nocookie.com/embed/" in js  # la CSP de nginx admite sólo ese dominio en frame-src
    assert "strict-origin-when-cross-origin" in js and "addEventListener('click'" in js


def test_cada_pagina_publica_enlaza_la_privacidad():
    paginas = [(r, _pagina(r)) for r in PUBLICAS if r != "/privacidad"] + [("login", login_html())]
    paginas += [(n, (STATIC / n).read_text(encoding="utf-8")) for n in ("probar.html", "index.html")]
    for nombre, html in paginas:
        assert 'href="/privacidad"' in html, nombre


def _claves_del_navegador():
    """Claves que el código guarda en el navegador (localStorage, sessionStorage o document.cookie)."""
    claves, constantes = set(), {}
    textos = [p.read_text(encoding="utf-8") for p in STATIC.glob("*.js")]
    textos += [p.read_text(encoding="utf-8") for p in STATIC.glob("*.html")]
    for texto in textos:
        constantes.update(dict(re.findall(r'\bconst\s+([A-Z_]+)\s*=\s*["\']([^"\']+)["\']', texto)))
    for texto in textos:
        assert "sessionStorage.setItem" not in texto and "document.cookie =" not in texto and "document.cookie=" not in texto
        for arg in re.findall(r"localStorage\.setItem\(\s*([^,]+),", texto):
            arg = arg.strip()
            if arg[0] in "'\"":
                claves.add(arg[1:-1])
            elif arg[0] == "`":
                claves.add(arg[1:].split("${", 1)[0])
            else:
                claves.add(constantes[arg])
    return claves


def test_cookies_y_almacenamiento_declarados_en_la_privacidad():
    html = _pagina("/privacidad")
    claves = _claves_del_navegador()
    assert claves == {"gobernanza-modo", "gobernanza_guia_informe_vista", "docente-visto-", "charla-proxima"}
    for clave in claves:
        assert f"<code>{clave}</code>" in html, clave
    # La única cookie del servidor es la de la sesión, y está declarada.
    cookies = set()
    for p in list((RAIZ / "routers").glob("*.py")) + list((RAIZ / "core").glob("*.py")) + [RAIZ / "main.py"]:
        cookies.update(re.findall(r"set_cookie\(\s*([A-Za-z_\"']+)", p.read_text(encoding="utf-8")))
    assert cookies == {"COOKIE_NAME"}
    assert f"<code>{COOKIE_NAME}</code>" in html


def test_robots_y_sitemap_incluyen_la_privacidad():
    assert "Allow: /privacidad" in client.get("/robots.txt").text
    assert "/privacidad</loc>" in client.get("/sitemap.xml").text
