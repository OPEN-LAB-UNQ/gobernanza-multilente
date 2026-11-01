import json
import re
from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient

from core.auth import login_html
from main import app
from versiones import ANALYSIS_VERSION, APP_VERSION, DOCUMENT_VERSION, version_codigo


class _Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, _tag, attrs):
        element_id = dict(attrs).get("id")
        if element_id:
            self.ids.append(element_id)


def test_presentacion_es_publica_institucional_y_explica_los_limites():
    client = TestClient(app)
    respuesta = client.get("/presentacion")
    assert respuesta.status_code == 200
    html = respuesta.text
    assert '<html lang="es">' in html
    assert "<title>Gobernanza Multilente · Una segunda lectura antes de decidir</title>" in html
    assert 'rel="canonical" href="https://gobernanza.entornodepruebas.com.ar/presentacion"' in html
    assert 'property="og:description"' in html
    assert "__PAGE_" not in html
    assert '<h1>Una segunda lectura antes de decidir.</h1>' in html
    assert 'En general, en pocos minutos tenés una revisión adicional que puede ayudarte a detectar puntos ciegos en tu informe.' in html
    assert 'Complementa tu revisión. La decisión sigue siendo tuya.' in html
    assert "ya sea en proceso de elaboración o terminados" in html
    assert 'un error que se te pasó' not in html  # no se presume que la persona se equivocó
    assert 'Detectar un solo error relevante' not in html  # no se presume que la persona se equivocó
    assert "doble lectura de un estudio médico" in html
    assert "qué quedó fuera de la evaluación y qué contexto o información adicional sería necesario considerar" in html
    assert 'class="hero-photo"' in html
    assert "hero-revision-institucional-sin-bandera.jpg" in html  # la foto de portada no lleva bandera

    recorrido = (
        'id="inicio"',
        'id="preguntas"',
        'id="ejemplos"',
        'id="prueba-institucional"',
    )
    assert [html.index(etapa) for etapa in recorrido] == sorted(html.index(etapa) for etapa in recorrido)
    for ancla in ("preguntas", "ejemplos", "prueba-institucional"):
        assert f'href="#{ancla}"' in html

    assert "59,0 → 66,7" in html
    assert "840 ≠ 790" in html
    assert "820 &gt; 760" in html
    assert "Para advertirlo hacen falta los componentes, sus pesos y el criterio declarado." in html
    assert "Ninguna de estas señales confirma por sí sola un error" in html
    assert 'href="/probar.html"' in html
    assert html.count('class="faq-lens"') == 7
    assert "No todas las lentes se ejecutan en todos los informes" in html
    assert "La coincidencia entre modelos no prueba" in html
    assert "ni fundamenta conformidad institucional" in html
    # El corte de pruebas vive en la ficha, no en la página principal.
    assert "Corte de pruebas técnicas" not in html and 'id="evidencia-publica"' not in html
    assert html.count('href="/detalle#validacion"') == 1  # solo en la pregunta «¿Cómo sabemos si funciona?»
    assert ">Evidencia</a>" not in html
    assert "Todavía falta medir con casos externos" in html
    assert "evaluación adversarial interna" in html and "No reemplaza una evaluación externa" in html
    assert "el uso real en una actividad formativa" in html and "no mide por sí solo su eficacia" in html
    assert "un ministerio" not in html and "no implica adopción ni aval de ningún organismo" in html
    # Las respuestas explican con ejemplos concretos y conservan la abstención como resultado.
    assert "un monto pagado mayor que el devengado" in html
    assert "Que no aparezcan señales no significa que el informe esté bien" in html
    assert "no recibe el archivo original" in html and "textos ya saneados" in html
    assert "pueden incluir valores del informe" in html
    # 25/10/2026: Gobernanza es un proyecto de OPEN LAB (UNQ); código MIT y documentación CC BY 4.0.
    assert "Proyecto de OPEN LAB (Universidad Nacional de Quilmes) en etapa piloto" in html
    assert "Proyecto independiente" not in html and "proyecto independiente" not in html
    assert "Código abierto bajo licencia MIT." in html and "Metodología y documentación bajo licencia CC BY 4.0." in html
    assert "No sustituye auditorías" in html
    assert "no es una certificación de veracidad ni una aprobación" in html
    assert "comprobante de los controles automáticos aplicados" in html
    assert "Alcance acordado con la institución" in html
    assert "10–20 informes cerrados" not in html
    assert "4–6 semanas" not in html
    assert "sin integración inicial con sistemas internos" in html
    assert 'Escribí a <strong>Maximiliano Pérez</strong>:' in html
    assert 'href="mailto:' not in html
    assert 'href="/detalle"' in html
    assert "Gobernanza Multilente, en pocas preguntas" in html
    # El posicionamiento se desarrolla en la respuesta correspondiente y aparece una sola vez.
    assert html.count("Lo que sigue siendo menos frecuente es encontrar arquitecturas concretas") == 1
    assert html.index('class="faq-toc"') < html.index('<summary id="faq-principios-practica">')
    assert "Existe bastante consenso sobre esos principios." in html
    assert "Concreta. Honesta. Humana." in html
    assert "lleva los principios de gobernanza a algo que se puede comprobar" in html  # descripción pública
    assert 'id="trayectoria"' in html
    assert "Gobernanza Multilente es otro proyecto de OPEN LAB y no fue el proyecto premiado" in html
    assert 'href="https://desarrollo2.entornodepruebas.com.ar/presentacion"' in html
    # La charla del ciclo UNQ se enlaza; el video de presentación queda detrás de un botón: el reproductor sin
    # cookies se crea recién al reproducirlo (tests/test_privacidad_ue.py).
    assert 'href="https://www.youtube.com/watch?v=Ty_CXHiCT5Q&amp;t=2410s"' in html
    assert "<iframe" not in html
    assert 'class="video-play" data-yt="iWddq1wAOrY"' in html and 'href="#video"' in html
    assert 'href="https://www.unq.edu.ar/noticias/distincion-internacional-del-bid-para-proyecto-de-extension-unq/"' in html
    assert "diez principios transversales en tres grupos" in html
    assert "trazabilidad, reproducibilidad y refutabilidad" in html
    # El contacto para preguntas aparece una sola vez, al final, y no debajo de cada respuesta.
    assert 'class="faq-contact"' not in html
    # Las preguntas no deben quedar tapadas por el encabezado fijo al navegar desde el índice.
    assert '.faq-list > details, .faq-list summary[id] { scroll-margin-top: 104px; }' in html
    assert html.count("maximilianoperez1981@gmail.com") == 1
    assert html.index('id="faq-mas-preguntas"') > html.index('id="prueba-institucional"')
    assert 'href="#faq-mas-preguntas"' not in html
    assert '<div hidden aria-hidden="true">' not in html
    assert 'id="inicio-detalle"' not in html
    assert 'id="procesamiento"' not in html
    assert 'id="constancia"' not in html
    assert 'href="#alcance"' not in html

    imagen = client.get("/hero-revision-institucional-sin-bandera.jpg", follow_redirects=False)
    assert imagen.status_code == 200
    assert imagen.headers["content-type"] == "image/jpeg"
    assert imagen.content == Path("static/hero-revision-institucional-sin-bandera.jpg").read_bytes()
    assert '<div class="trajectory-logo">' not in html  # la copia pública no lleva el logo de la UNQ


def test_detalle_es_una_ficha_institucional_consistente_con_el_comprobante():
    respuesta = TestClient(app).get("/detalle")
    assert respuesta.status_code == 200
    assert "<title>Ficha técnica · Gobernanza Multilente</title>" in respuesta.text
    assert 'rel="canonical" href="https://gobernanza.entornodepruebas.com.ar/detalle"' in respuesta.text
    assert 'property="og:description"' in respuesta.text
    assert "__PAGE_" not in respuesta.text
    assert "Metodología, resguardos y estado de validación" in respuesta.text
    assert "Una segunda lectura antes de decidir." not in respuesta.text
    assert 'id="preguntas"' not in respuesta.text
    assert 'id="ejemplos"' not in respuesta.text
    assert 'href="/presentacion"' in respuesta.text
    assert "Una explicación técnica de cada mirada" in respuesta.text
    assert respuesta.text.count('class="lens"') == 7
    # Se agrega el lector del cuadro a los seis bloques; se conservan las anclas históricas.
    assert respuesta.text.count('class="ficha-block"') == 8  # 0.10.35: «Revisión rápida y revisión profunda»
    # Una sola paleta (roja) en todas las páginas públicas: presentación, ficha, demo y acceso.
    assert "body.page-landing, body.page-detail {" in respuesta.text
    for azul in ("#2f70e8", "#315fbb", "#174b9e"):
        assert azul not in respuesta.text
        assert azul not in Path("static/probar.html").read_text(encoding="utf-8")
    assert "#1f4d78" not in login_html() and "#b01c2e" in login_html()
    assert 'class="ficha-toc"' in respuesta.text
    for ancla in ("alcance", "modulos", "metodologia", "lentes", "procedimiento", "reglas-ia-detalle", "procesamiento",
                  "constancia", "validacion", "limites", "prueba-detalle", "contacto-detalle", "documentacion"):
        assert respuesta.text.count(f'id="{ancla}"') == 1
    assert "Maxi Pérez" not in respuesta.text
    assert "La autorización institucional es un requisito de uso" in respuesta.text
    assert "hasta cinco filas ya saneadas" in respuesta.text
    assert "OpenAI y Google Gemini" in respuesta.text
    assert "Una lista vacía de modelos no desactiva la triangulación" in respuesta.text
    assert "El comprobante documenta una ejecución, no una aprobación" in respuesta.text
    evidence = json.loads(Path("static/public-evidence.json").read_text(encoding="utf-8"))["tests"]
    assert f'{evidence["passed"]} / {evidence["collected"]}' in respuesta.text
    assert f'pruebas incluidas: {evidence["collected"]}' in respuesta.text
    assert f'fallidas: {evidence["failed"]}' in respuesta.text
    assert evidence["date"] in respuesta.text
    assert version_codigo()[:12] in respuesta.text
    assert f"aplicación {APP_VERSION}" in respuesta.text
    assert f"motor {ANALYSIS_VERSION}" in respuesta.text
    assert f"documento metodológico v{DOCUMENT_VERSION}" in respuesta.text
    assert "255 pruebas" not in respuesta.text
    assert "Las 286 pruebas automatizadas de esta versión pasan" not in respuesta.text
    assert "informes ya cerrados y resultado conocido" in respuesta.text
    assert 'href="https://doi.org/10.5281/zenodo.22063241"' in respuesta.text  # serie
    assert 'href="https://doi.org/10.5281/zenodo.23851688"' in respuesta.text  # versión 9.4
    assert "zenodo.[versión anterior]" not in respuesta.text  # la 9.2 ya no es la vigente
    assert "No se encontró todavía un DOI" not in respuesta.text
    assert "no aporta valor suficiente" in respuesta.text
    assert "cantidad de casos, duración, permisos, proveedores" in respuesta.text
    assert "10–20" not in respuesta.text
    assert "4–6 semanas" not in respuesta.text
    assert "B-1 v1.2" not in respuesta.text
    assert "35 casos" not in respuesta.text
    assert "16 planillas" not in respuesta.text
    assert "sin costo ni integraciones" not in respuesta.text
    assert "Descargar Word" not in respuesta.text
    assert 'href="/Gobernanza-Multilente-Incubadora-Monitoreo-' not in respuesta.text
    documentos_no_publicos = (
        "/Gobernanza-Multilente-Incubadora-Monitoreo-v0.7.0-CORREGIDO.docx",
        "/Gobernanza-Multilente-Incubadora-Monitoreo-v0.7.3.docx",
        "/Gobernanza-Multilente-Incubadora-Monitoreo-v0.7.4.docx",
        "/Gobernanza-Multilente-Incubadora-Monitoreo-v0.7.5.docx",
        "/Gobernanza-Multilente-Incubadora-Monitoreo-v5.docx",
    )
    for documento in documentos_no_publicos:
        descarga = TestClient(app).get(documento, follow_redirects=False)
        assert descarga.status_code == 303
        assert descarga.headers["location"] == "/login"
    restringido = TestClient(app).get("/tecnico.html", follow_redirects=False)
    assert restringido.status_code == 303
    assert restringido.headers["location"] == "/login"


def test_presentacion_no_repite_ids_y_esta_enlazada():
    client = TestClient(app)
    for ruta in ("/presentacion", "/detalle"):
        html = client.get(ruta).text
        parser = _Ids()
        parser.feed(html)
        assert len(parser.ids) == len(set(parser.ids))
        for target in re.findall(r'href="#([^"]+)"', html):
            assert target in parser.ids, (ruta, target)
        assert html.count("<h1") == 1
        assert "__PAGE_" not in html
    assert 'href="/presentacion"' in Path("static/index.html").read_text(encoding="utf-8")
    assert 'href="/presentacion"' in login_html()
    assert 'href="/probar.html"' in login_html()


def test_objetivo_y_marco_modular_coinciden_en_ambas_paginas():
    client = TestClient(app)
    for route in ("/presentacion", "/detalle"):
        html = client.get(route).text
        assert ("informes con datos agregados, terminados o en elaboración" in html
                or "informes con datos agregados, ya sea en proceso de elaboración o terminados" in html)
        if route == "/detalle":  # La presentación se concentra en Multilente; los módulos se explican en la ficha.
            for module in ("Incubadora", "Conexiones", "Monitoreo"):
                assert module in html
        if route == "/detalle":
            assert "La interpretación y la decisión siguen siendo humanas." in html
    detail = client.get("/detalle").text
    assert "no son etapas obligatorias" in detail
    assert "R-1, una evaluación opcional y separada" in detail
    assert "no incorporar tecnología" in detail
    assert "pre-devolución automática identificada como IA" in detail
    assert "No es una calificación ni la devolución docente" in detail
    assert "notas de orientación del docente responsable" in detail
    assert "Cuándo la consideramos usable" in detail and "antes de conocer el resultado de la medición" in detail
    assert "Obsidian" not in detail  # las notas personales del docente no se nombran en la ficha pública


def test_preguntas_son_la_entrada_y_lentes_pertenecen_a_como_funciona():
    html = TestClient(app).get("/presentacion").text
    main = html.split("  <main>", 1)[1].split("  </main>", 1)[0]
    sections = re.findall(r'<section[^>]+id="([^"]+)"', main)
    # 0.10.42 (orden aprobado por Maxi): portada, problema e idea, cómo funciona, dos revisiones, medido, probalo.
    # 0.10.41.7 (pedido de Maxi): el video de presentación va después de la portada.
    assert sections == ["inicio", "video", "sintesis", "como-funciona", "dos-revisiones", "medido", "probalo", "uso", "principios",
                        "criterio", "preguntas", "ejemplos", "trayectoria", "prueba-institucional"]
    # Cada sección propia lleva su etiqueta chica y un H2; no hay párrafos sueltos en negrita grande.
    for seccion in ("video", "sintesis", "como-funciona", "dos-revisiones", "medido", "probalo"):
        bloque = main.split(f'id="{seccion}"', 1)[1].split("</section>", 1)[0]
        assert bloque.count('class="section-kicker"') == 1 and bloque.count("<h2>") == 1, seccion
        assert 'class="approach-lead"' not in bloque and 'class="sintesis-recorrido"' not in bloque, seccion
    pasos = main.split('id="como-funciona"', 1)[1].split("</section>", 1)[0]
    # 0.10.41.5: el lema y los cinco pasos alternados (IA, persona, reglas, IA, persona).
    assert "<h2>La IA propone, las reglas comprueban, la persona decide.</h2>" in pasos
    assert "Primero dice qué no miró" in pasos.split("<ol", 1)[0]
    assert pasos.count("<h3>") == 5
    h3 = re.findall(r"<h3>([^<]+)</h3>", pasos)
    assert h3 == ["La IA interpreta", "La persona confirma", "Las reglas comprueban", "La IA lee las señales", "La persona decide"]
    assert re.findall(r'paso-actor-(\w+)', pasos) == ["ia", "persona", "reglas", "ia", "persona"]
    assert "La revisión rápida usa sólo reglas y persona (pasos 3 y 5): los datos no salen del servidor." in pasos
    assert "Una diferencia es un motivo para revisar. No demuestra por sí sola cuál dato está mal." in pasos
    assert main.index('id="sintesis"') < main.index("Gobernanza no da veredictos: hace preguntas.") < main.index('id="como-funciona"')
    # Bloque visible de enfoque: texto del responsable, a la vista antes de las preguntas.
    enfoque = main.split('id="principios"', 1)[1].split('id="preguntas"', 1)[0]
    assert "De los principios a un dispositivo operativo" in enfoque
    assert "ya forman parte de los principales marcos de gobernanza de IA" in enfoque
    assert "trabaja en el paso siguiente: cómo hacer visibles esos principios en una revisión concreta" in enfoque
    assert enfoque.count("<li>") == 5 and "Muestra qué no pudo evaluarse." in enfoque
    assert "No propone nuevos principios. Propone una forma concreta de llevarlos a la práctica y poder contrastar cómo fueron aplicados." in enfoque
    # «De los principios a la práctica» es una de las preguntas, en lenguaje llano y sin confrontar con otros marcos.
    assert 'href="#faq-principios-practica"' in main
    puente = main.split('<summary id="faq-principios-practica">', 1)[1].split('<summary id="faq-principios">', 1)[0]
    assert "se traducen en mecanismos concretos" in puente
    assert "se aplican, se registran y se revisan en situaciones reales" in puente
    for principio in ("Trazabilidad", "Supervisión humana", "Transparencia", "Gestión de riesgos", "Responsabilidad"):
        assert f"<li><strong>{principio}:</strong>" in puente
    assert "lo explicita en lugar de forzar una conclusión" in puente
    assert "se automatizan verificaciones y controles, no las decisiones" in puente
    # Marcos nombrados para lectores institucionales (pedido del 11/10): diálogo, no cumplimiento.
    assert "Carta Iberoamericana de Inteligencia Artificial en la Administración Pública del CLAD" in puente
    assert "OCDE y la UNESCO" in puente and "sin presentarlo como certificación ni cumplimiento" in puente
    assert 'href="https://doi.org/10.5281/zenodo.22063241"' in puente
    for jerga in ("huella", "SHA", "lentes", "B-1", "API", "versión del motor"):
        assert jerga not in puente
    for confrontativa in ("se quedan en principios", "solo hablan", "supera a", "resuelve definitivamente"):
        assert confrontativa not in puente
    answer = main.split('<summary id="faq-como-funciona">', 1)[1].split('<summary id="faq-que-produce">', 1)[0]
    assert answer.count('class="faq-lens"') == 7
    # Ejemplo físico-financiero de la Orquesta (pedido del 11/10): pregunta, no veredicto.
    orquesta = answer.split("<strong>Orquesta</strong>", 1)[1].split("</details>", 1)[0]
    assert "ejecutó el 90 % de su presupuesto y cumplió el 30 % de sus metas físicas" in orquesta
    assert "pregunta qué explica la diferencia entre el avance físico y la ejecución presupuestaria" in orquesta
    assert "la decisión" in answer.lower()


def test_niveles_lentes_y_evidencia_no_prometen_certeza():
    client = TestClient(app)
    for route in ("/presentacion", "/detalle"):
        html = client.get(route).text
        for level in ("Verificación determinística", "Interpretación contextual", "Exploración"):
            assert level in html
        assert "no una escala de certeza" in html or "ni una escala de certeza" in html
        assert "Cinco capas" not in html
        assert "No todos los resultados tienen la misma certeza" not in html
    detail = client.get("/detalle").text
    evidencia = json.loads(Path("static/public-evidence.json").read_text(encoding="utf-8"))
    assert "Identificador del código Python probado" in detail
    assert str(evidencia.get("code_fingerprint") or "no registrada")[:12] in detail
    assert "__TEST_CODE_VERSION__" not in detail
    assert "hubo cambios de código posteriores" in detail


def test_fuente_propia_se_carga_sin_sesion_en_ambas_paginas():
    client = TestClient(app)
    fuente = "/fonts/inter-variable-v4.woff2"
    for ruta in ("/presentacion", "/detalle"):
        html = client.get(ruta).text
        assert f'href="{fuente}" as="font" type="font/woff2" crossorigin' in html
        assert f'url("{fuente}") format("woff2")' in html
        assert 'font-family: "Gobernanza Inter";' in html
        assert 'font-family: var(--font-institucional);' in html
        assert 'font-weight: 100 900;' in html
        assert 'font-optical-sizing: none;' in html
        assert 'font-size: clamp(1.125rem, 1.65vw, 1.25rem);' in html
        assert 'font-weight: 850;' not in html
        assert 'fonts.googleapis.com' not in html
        assert 'fonts.gstatic.com' not in html
    response = client.get(fuente, follow_redirects=False)
    assert response.status_code == 200
    assert response.headers['content-type'] == 'font/woff2'
    assert response.content.startswith(b'wOF2')
    assert response.content == Path('static' + fuente).read_bytes()
    licencia = client.get('/fonts/Inter-OFL.txt', follow_redirects=False)
    assert licencia.status_code == 200
    assert 'SIL OPEN FONT LICENSE Version 1.1' in licencia.text


def test_publicar_fuente_no_abre_otros_archivos_ni_api():
    client = TestClient(app)
    for ruta in ('/fonts/no-autorizado.txt', '/tecnico.html', '/index.html'):
        response = client.get(ruta, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'] == '/login'
    assert client.get('/api/informes').status_code == 401
    assert client.post('/api/analisis-rapido').status_code == 401
    pagina = client.get('/probar.html', follow_redirects=False)
    assert pagina.status_code == 200
    assert 'Explorá informes predefinidos sin clave' in pagina.text
    catalogo = client.get('/api/ejemplos/publicos')
    assert catalogo.status_code == 200
    assert len(catalogo.json()['casos']) == 8
    assert catalogo.json()['nuevas_cargas_requieren_clave'] is True
    for caso in range(1, 9):
        zip_publico = client.get(f'/api/ejemplos/publicos/{caso}/zip')
        assert zip_publico.status_code == 200
        assert zip_publico.content.startswith(b'PK')
        for lado in ('sin', 'con'):
            assert client.get(f'/api/ejemplos/publicos/{caso}/{lado}.pdf').content.startswith(b'%PDF')
            original = client.get(f'/api/ejemplos/publicos/{caso}/{lado}.xlsx')
            assert original.content.startswith(b'PK')
            assert original.headers['content-disposition'].startswith('attachment;')
    assert client.get('/api/ejemplos/publicos/1/otro.pdf').status_code == 401
    assert client.get('/api/ejemplos/publicos/9/zip').status_code == 401


def test_criterio_de_uso_de_ia_esta_en_la_presentacion():
    html = TestClient(app).get("/presentacion").text
    assert 'id="criterio"' in html and "Criterio de uso" in html
    for frase in [
        "La salida de la IA nunca se entrega cruda.",
        "se revisa, se corrige, se contrasta y se asume",
        "La IA es insumo, nunca producto",
        "La IA correlaciona, el humano comprende",
        "El sistema no aprende: se calibra",
        "La gobernanza no depende de quién revise: todos aplican las mismas reglas",
    ]:
        assert frase in html, frase
    assert 'id="faq-checklist"' in html and 'id="faq-responsabilidad"' in html
    assert "no existe «lo hizo la IA»" in html
    assert "una decisión de la que nadie se hace responsable no es gobierno" in html


def test_presentacion_habla_a_organismos_y_organizaciones():
    html = TestClient(app).get("/presentacion").text
    assert "Revisión institucional" not in html
    assert "cooperativas, ONG y universidades" in html
    for ambito in ("Organismo público", "Empresa o cooperativa", "Cooperativa, ONG o pyme"):
        assert f'<span class="example-scope">{ambito}</span>' in html
    assert "conveniencia política" not in html and "responsabilidad administrativa" not in html
    assert ">Ponerlo a prueba</a>" in html


def test_caso_real_gpsdn_y_tabla_de_mediciones():
    raiz = Path(__file__).resolve().parents[1] / "static"
    presentacion = (raiz / "presentacion.html").read_text(encoding="utf-8")
    assert 'id="caso-real"' in presentacion and "en una jurisdicción, un total cargado a mano pasó exactamente" in presentacion
    ficha = (raiz / "detalle-body.html").read_text(encoding="utf-8")
    assert 'class="ficha-tabla"' in ficha and "Detalle de cada medición" in ficha
    assert "Hoy hay cinco fuentes:" in presentacion and 'id="verificacion-independiente-resumen"' in presentacion
    assert 'href="/detalle#verificacion-independiente"' in presentacion and 'id="verificacion-independiente"' in ficha
    assert "Pruebas de invariancia." in ficha and "Verificador independiente." in ficha and "no reemplazan la prueba ciega externa" in ficha
    assert "diez minutos" not in presentacion
    assert 'href="#faq-todos-los-errores"' in presentacion and '<summary id="faq-todos-los-errores">¿Encuentra todos los errores?</summary>' in presentacion
    assert "invita a dejar de mirar" in presentacion and "Ninguna de sus piezas es nueva por separado" in presentacion
    assert "Sigue pendiente un conjunto formal" not in ficha and "banco interno de calibración" in ficha
    assert "bajar las alarmas sobre series irregulares" not in ficha and "83 pruebas de JavaScript" in ficha
    assert "esos datos no se envían a proveedores de IA" in ficha and "tope diario de análisis con IA" in ficha


def test_que_archivos_lee_excel_csv_y_pdf_con_revision_de_lectura():
    texto = (
        "Multilente analiza Excel y CSV con cuadros de datos agregados. Los PDF y las imágenes pasan antes por "
        "una revisión de lectura: ves el original al lado de la tabla leída, corregís lo necesario y confirmás; "
        "recién ahí se analiza. No lee Word ni datos individuales."
    )
    client = TestClient(app)
    presentacion = client.get("/presentacion").text
    assert '<summary id="faq-que-archivos">¿Qué archivos puede leer?</summary>' in presentacion
    assert 'href="#faq-que-archivos"' in presentacion
    assert texto in presentacion and "no se envían a proveedores de IA" in presentacion
    raiz = Path(__file__).resolve().parents[1] / "static"
    ficha = (raiz / "detalle-body.html").read_text(encoding="utf-8")
    alcance = ficha.split('id="alcance"', 1)[1].split("</section>", 1)[0]
    assert texto in alcance
    index = (raiz / "index.html").read_text(encoding="utf-8")
    assert "Excel o CSV. Los PDF y las imágenes pasan antes por la revisión de lectura." in index
    assert "En PDF, la cobertura depende" not in index and 'id="opt-limite-paginas-pdf"' not in index
    for html in (presentacion, ficha, index):
        assert "CSV, Excel o PDF" not in html and "CSV, Excel y PDF" not in html


def test_la_app_ya_no_ofrece_el_boton_de_sugerencias():
    # Cohorte nueva (octubre de 2026): el botón se retiró; las sugerencias guardadas se conservan.
    index = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "sugerencias.js" not in index


def test_segunda_lectura_sistematica_y_respuesta_al_chat():
    html = (Path(__file__).resolve().parents[1] / "static" / "presentacion.html").read_text(encoding="utf-8")
    assert "no escala. Gobernanza sistematiza esa segunda lectura" in html


def test_reglas_para_lo_que_se_calcula_ia_para_interpretar():
    html = (Path(__file__).resolve().parents[1] / "static" / "presentacion.html").read_text(encoding="utf-8")
    assert "Gobernanza usa reglas para lo que se puede calcular y deja la IA para lo que necesita interpretación." in html


def test_en_pocas_palabras_resume_problema_que_hace_y_que_no_es():
    # Pedido del 13/10/2026: la presentación sigue la síntesis de los correos al BID.
    html = TestClient(app).get("/presentacion").text
    bloque = html.split('id="sintesis"', 1)[1].split("</section>", 1)[0]
    assert "Gobernanza no da veredictos: hace preguntas." in bloque
    assert "Quien decide casi nunca tiene tiempo de revisar a fondo todos los informes." in bloque
    assert "cómo se cargó, acumuló o reclasificó el dato" in bloque
    assert "No es una herramienta antifraude ni de auditoría forense, y no atribuye responsabilidades." in bloque
    assert "Está pensada para datos agregados: no se cargan datos de personas." in bloque
    # 0.10.42: el recorrido ya no se repite en un párrafo; lo cuentan los tres pasos de «Cómo funciona».
    como = html.split('id="como-funciona"', 1)[1].split("</section>", 1)[0]
    assert "decisión humana trazable" in como
    assert 'href="#faq-como-funciona"' in como
    # La portada no repite el problema: queda en el bloque.
    portada = html.split('id="inicio"', 1)[1].split("</section>", 1)[0]
    assert "Quien decide casi nunca" not in portada


def test_multilente_publica_la_charla_sin_pedir_sesion():
    # Pedido del 14/10/2026: charla del Encuentro Nacional de Tecnología Cívica (Guadalajara).
    respuesta = TestClient(app).get("/multilente", follow_redirects=False)
    assert respuesta.status_code == 200
    html = respuesta.text
    assert "<title>Gobernanza Multilente · Una segunda lectura antes de decidir (charla)</title>" in html
    assert 'rel="canonical" href="https://gobernanza.entornodepruebas.com.ar/multilente"' in html
    assert '<meta property="og:locale" content="es_AR">' in html
    main = html.split("  <main>", 1)[1].split("  </main>", 1)[0]
    assert 'id="inicio"' not in main  # no es la presentación con otro título
    for texto in (
        "Imaginen un subsecretario, un secretario, que tiene que tomar una decisión.",
        "El alfil que estaba en las casillas blancas de golpe aparece en las negras.",
        "Fórmula alterada y valor pegado",
        "la condición quedó escrita a mano, «Promociona», donde la fórmula da REGULAR.",
        "No buscamos veredictos: hacemos preguntas. Buscamos detectar puntos ciegos.",
        "ya justificó con creces tener esa segunda mirada.",
        "La máquina correlaciona; la persona comprende.",
    ):
        assert texto in main
    # Cuentas del ejemplo de las notas: en G4 el promedio simple y el ponderado dan 7; en H3 la fórmula da REGULAR.
    pesos = (0.15, 0.15, 0.2, 0.5)
    g4 = (7, 7, 7, 7)
    assert round(sum(p * v for p, v in zip(pesos, g4)), 2) == sum(g4) / 4 == 7
    g3 = round(sum(p * v for p, v in zip(pesos, (5, 5, 6, 6))), 2)
    assert g3 == 5.7 and not (g3 >= 7) and g3 >= 4 and 0.7 >= 0.6  # REGULAR, no PROMOCIONA
    assert "cambió el criterio" in main
    for enlace in ('href="/presentacion"', 'href="/probar.html"', 'href="/detalle"'):
        assert enlace in main


def test_multilente_no_suma_entradas_al_menu_de_la_presentacion():
    html = TestClient(app).get("/presentacion").text
    assert 'href="/multilente"' not in html


def test_licencias_y_autoria_open_lab():
    """25/10/2026: LICENSE MIT en la raíz; la ficha no dice «desarrollo independiente» (contradiría OPEN LAB)."""
    raiz = Path(__file__).resolve().parents[1]
    licencia = (raiz / "LICENSE").read_text(encoding="utf-8")
    assert licencia.startswith("MIT License") and "Copyright (c) 2026 Maximiliano Pérez · OPEN LAB - UNQ" in licencia
    ficha = (raiz / "static" / "detalle-body.html").read_text(encoding="utf-8")
    assert "desarrollo independiente" not in ficha and "<strong>Licencia MIT</strong>" in ficha
    assert "Gobernanza Multilente es un desarrollo distinto de esa iniciativa" in ficha


def test_el_lema_reemplaza_a_la_cuenta_comprueba_en_todos_lados():
    """0.10.41.5: «La IA propone, las reglas comprueban, la persona decide.» en lugar de «La IA propone; la cuenta comprueba»."""
    raiz = Path(__file__).resolve().parents[1]
    for nombre in ("presentacion.html", "detalle-body.html", "multilente-body.html", "index.html", "app.js", "interpretacion.js"):
        texto = (raiz / "static" / nombre).read_text(encoding="utf-8")
        assert "la cuenta comprueba" not in texto.lower() and "las reglas hacen la cuenta" not in texto, nombre
    for nombre in ("presentacion.html", "detalle-body.html", "multilente-body.html"):
        assert "La IA propone, las reglas comprueban, la persona decide." in (raiz / "static" / nombre).read_text(encoding="utf-8")
    charla = (raiz / "static" / "multilente-body.html").read_text(encoding="utf-8")
    assert "Nuevo · Interpretar, confirmar y controlar" not in charla



