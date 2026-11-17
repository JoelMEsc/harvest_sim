"""Dashboard con datos y artefactos existentes, sin ejecutar la simulación."""
import base64
import csv
from html.parser import HTMLParser
import json

import pytest

from test_viewer import cargar_script, trace_de_prueba


class InspeccionHTML(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.secciones = []
        self.imagenes = []
        self.scripts = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section":
            self.secciones.append(attrs["id"])
        elif tag == "img":
            self.imagenes.append(attrs)
        elif tag == "script":
            self.scripts.append(attrs)


@pytest.fixture
def dashboard():
    return cargar_script("viz/dashboard.py")


def preparar(tmp_path, trace):
    carpeta = tmp_path / trace["config"]["nombre"]
    carpeta.mkdir()
    (carpeta / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
    return carpeta


def test_tres_paneles_y_escenarios_del_equipo(dashboard, tmp_path):
    generador = cargar_script("tools/generar_trace_ejemplo.py")
    rutas = generador.generar_escenarios(tmp_path / "ejemplo")
    salida = tmp_path / "dashboard.html"
    assert dashboard.main([*[str(p.parent) for p in rutas], "--salida", str(salida)]) == 0
    html = salida.read_text()
    assert InspeccionHTML(html).secciones == ["entorno", "indicadores", "experimental"]
    assert all(nombre in html for nombre in ("ejemplo_a", "ejemplo_b", "ejemplo_c"))
    assert "Datos de ejemplo" in html and "Parámetros por escenario" in html
    assert "No disponible" in html and "Sin cuadros" in html
    assert "4 × 3" in html and "5 × 3" in html


def test_metricas_unidades_y_valores_cero(dashboard, tmp_path):
    carpeta = preparar(tmp_path, trace_de_prueba())
    salida = dashboard.generar_dashboard([carpeta], tmp_path / "dashboard.html")
    html = salida.read_text()
    assert '<strong>50</strong><span>%</span>' in html
    assert '<strong>0</strong><span>eventos</span>' in html
    assert '<strong>2</strong><span>celdas</span>' in html
    assert "Transferencia (u./tick)" in html
    assert "No disponible" not in html


def test_imagenes_portables_tablas_y_escape_de_html(dashboard, monkeypatch, tmp_path):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    viewer = cargar_script("viz/viewer.py")
    trace = trace_de_prueba()
    trace["meta"]["escenario"] = '<script>alert("x")</script>'
    carpeta = preparar(tmp_path, trace)
    png = viewer.guardar_cuadros(viewer.Reproductor(trace), carpeta / "cuadros", 20)[0].read_bytes()
    viewer.pygame.quit()
    (carpeta / "plots").mkdir()
    for nombre, _, _ in dashboard.GRAFICAS:
        (carpeta / "plots" / nombre).write_bytes(png)
    comparacion = tmp_path / "otras_comparaciones"
    comparacion.mkdir()
    (comparacion / "comparacion_escenarios.png").write_bytes(png)
    with (comparacion / "resumen.csv").open("w", newline="") as archivo:
        csv.writer(archivo).writerows([["escenario", "tiempo"], ["<img src=x>", 20]])
    experimento = tmp_path / "experimentos" / "transferencia"
    experimento.mkdir(parents=True)
    (experimento / "sensibilidad_tasa_transferencia.png").write_bytes(png)
    (experimento / "resumen.csv").write_text("escenario,media\nprueba_a,20\n")
    salida = dashboard.generar_dashboard([carpeta], tmp_path / "pagina.html", comparacion, experimento.parent)
    html = salida.read_text()
    estructura = InspeccionHTML(html)
    assert not estructura.scripts
    assert len(estructura.imagenes) == 10  # dos cuadros, seis gráficas, comparación, sensibilidad
    cuadros = {p.read_bytes() for p in (carpeta / "cuadros").glob("*.png")}
    for imagen in estructura.imagenes:
        assert imagen["alt"] and imagen["src"].startswith("data:image/png;base64,")
        assert base64.b64decode(imagen["src"].split(",")[1]) in cuadros
    assert "&lt;script&gt;" in html and "&lt;img src=x&gt;" in html
    assert str(tmp_path) not in html
    assert "Resumen estadístico del barrido" in html


def test_errores_sin_dejar_html_incompleto(dashboard, tmp_path, capsys):
    salida = tmp_path / "pagina.html"
    assert dashboard.main([str(tmp_path), "--salida", str(salida)]) == 2
    assert "error:" in capsys.readouterr().err and not salida.exists()
    carpeta = preparar(tmp_path, trace_de_prueba())
    (carpeta / "cuadros").mkdir()
    (carpeta / "cuadros" / "tick_000000.png").write_text("no es un png")
    assert dashboard.main([str(carpeta), "--salida", str(salida)]) == 2
    assert "PNG" in capsys.readouterr().err and not salida.exists()
