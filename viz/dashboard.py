"""Dashboard local (§7): lee resultados ya generados; no ejecuta la simulación.

python viz/dashboard.py runs/escenario_a runs/escenario_b runs/escenario_c --salida runs/dashboard.html
Los cuadros se leen de <escenario>/cuadros/tick_*.png (viewer.py --guardar-cuadros).
Las imágenes se incrustan para poder compartir el HTML sin archivos auxiliares.
"""
from __future__ import annotations

import argparse
import base64
import csv
from html import escape
import json
from pathlib import Path
import sys

GRAFICAS = [
    ("1_linea_de_tiempo_estados.png", "Estados de los agentes", "¿Qué hace cada agente en cada tick?"),
    ("2_ocioso_acumulado.png", "Tiempo ocioso acumulado", "¿Cuántos ticks ha esperado la cosechadora?"),
    ("3_distancia_cosechadora_carro.png", "Distancia al carro", "¿Qué tan lejos está el carro más cercano, en celdas?"),
    ("4_flujo_del_grano.png", "Flujo del grano", "¿Cuántas unidades de grano llegan a bodega y cuántas van en tránsito?"),
    ("5_mapa_espera.png", "Mapa de espera", "¿En qué celdas se acumulan los ticks de espera?"),
    ("6_mapa_trafico.png", "Mapa de tráfico", "¿Cuántas visitas recibe cada celda?"),
]
INDICADORES = [
    ("tiempo_completacion", "Completación", "ticks"),
    ("tiempo_ocioso_cosechadora", "Tiempo ocioso", "ticks / cosechadora"),
    ("porcentaje_ocioso", "Ocio", "%"),
    ("distancia_cosechadora_carro_promedio", "Distancia media al carro", "celdas"),
    ("utilizacion_carro", "Utilización del carro", "%"),
    ("ticks_bloqueados", "Bloqueos", "eventos"),
]
CSS = """
:root{color-scheme:light;--ink:#20372d;--green:#267449;--muted:#607067;--paper:#f5f3e9;--line:#d8dfd7}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}
a{color:var(--green)}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #c79820;outline-offset:4px}
header{background:var(--ink);color:#fff;padding:48px max(24px,calc((100vw - 1200px)/2)) 34px}
header p{color:#d6e3d8;max-width:730px}.eyebrow{text-transform:uppercase;letter-spacing:.16em;font-size:12px;font-weight:700}
h1{font-size:clamp(32px,5vw,56px);line-height:1.1;letter-spacing:-.04em;margin:14px 0 20px}h2{font-size:30px;margin:0}h3{font-size:22px;margin:0 0 14px}h4{font-size:18px;margin:0 0 8px}
nav{display:flex;gap:12px;flex-wrap:wrap;margin-top:28px}nav a{color:#fff;text-decoration:none;border:1px solid #718779;border-radius:6px;padding:9px 18px}
nav a:hover{background:#355342}main{max-width:1248px;margin:auto;padding:36px 24px}section{scroll-margin-top:24px;margin-bottom:64px}
.section-head{border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:24px}.section-head .eyebrow{color:var(--green)}.muted{color:var(--muted)}
article,.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:24px;margin:18px 0}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
figure{margin:0;min-width:0}figure img{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:6px}figcaption{font-size:14px;color:var(--muted);margin:10px 0 20px}
.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0 26px}.metric{background:var(--paper);border-radius:8px;padding:16px}.metric strong{display:block;font-size:30px;line-height:1.3}.metric span{display:block;font-size:13px;color:var(--muted)}
.missing{border:1px dashed #a3ada5;border-radius:8px;padding:20px;background:#fafaf7;color:var(--muted);overflow-wrap:anywhere}.table-scroll{overflow:auto;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:12px 16px;border-bottom:1px solid var(--line);white-space:nowrap}th{background:#edf1eb}caption{text-align:left;font-weight:600;padding:0 0 12px}
.frames{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:20px}.frames figure{flex:0 0 100%;scroll-snap-align:start}.frames:focus-visible{outline:3px solid #c79820}.badge{display:inline-block;background:#e9d9a5;color:#473b17;border-radius:4px;padding:4px 10px;font-size:13px}
footer{border-top:1px solid var(--line);padding:24px;color:var(--muted);font-size:14px}details{margin:16px 0}summary{cursor:pointer;font-weight:600}code{overflow-wrap:anywhere}
@media(max-width:760px){.grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}article,.card{padding:16px}header{padding:32px 20px}main{padding:26px 16px}}
@media print{header{background:white;color:var(--ink);padding:0}header p{color:var(--ink)}nav{display:none}main{padding:0}.frames{display:block}.frames figure{break-inside:avoid}.grid{display:block}.grid figure{break-inside:avoid}details{display:block}article{break-inside:auto}section{margin-bottom:24px}}
"""


def imagen(ruta, titulo, pregunta):
    if not ruta.is_file():
        return f'<div class="missing"><strong>{escape(titulo)}</strong><br>Falta {escape(ruta.name)}.</div>'
    contenido = ruta.read_bytes()
    if not contenido.startswith(b"\x89PNG\r\n\x1a\n") or len(contenido) < 24:
        raise ValueError(f"no es un PNG válido: {ruta}")
    ancho = int.from_bytes(contenido[16:20], "big")
    alto = int.from_bytes(contenido[20:24], "big")
    src = base64.b64encode(contenido).decode("ascii")
    return (f'<figure><img src="data:image/png;base64,{src}" alt="{escape(titulo)}" width="{ancho}" height="{alto}" loading="lazy">'
            f'<figcaption><strong>{escape(titulo)}.</strong> {escape(pregunta)}</figcaption></figure>')


def tabla(titulo, encabezados, filas):
    cabecera = "".join(f'<th scope="col">{escape(str(c))}</th>' for c in encabezados)
    cuerpo = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in fila) + "</tr>" for fila in filas)
    return f'<div class="table-scroll"><table><caption>{escape(titulo)}</caption><thead><tr>{cabecera}</tr></thead><tbody>{cuerpo}</tbody></table></div>'


def tabla_csv(ruta, titulo):
    if not ruta.is_file():
        return f'<p class="missing">Falta {escape(ruta.name)}: {escape(titulo)}.</p>'
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.reader(archivo))
    if not filas:
        return '<p class="missing">La tabla está vacía.</p>'
    return tabla(titulo, filas[0], filas[1:])


def valor_metrica(metricas, clave):
    valor = metricas.get(clave)
    if valor is None:
        return "No disponible"
    if clave == "utilizacion_carro":
        valor *= 100
    return f"{valor:,.2f}".rstrip("0").rstrip(".") if isinstance(valor, (float, int)) else str(valor)


def generar_dashboard(carpetas, salida, comparacion=None, experimentos=None):
    carpetas = [Path(p) for p in carpetas]
    if not carpetas:
        raise ValueError("indica al menos un escenario")
    comparacion = Path(comparacion) if comparacion else carpetas[0].parent / "comparacion"
    experimentos = Path(experimentos) if experimentos else carpetas[0].parent / "experimentos"
    escenarios = []
    for carpeta in carpetas:
        with (carpeta / "trace.json").open(encoding="utf-8") as archivo:
            trace = json.load(archivo)
        if trace.get("schema_version") not in ("2.1", "2.2"):
            raise ValueError(f"{carpeta.name}: se requiere trace 2.1 o 2.2")
        escenarios.append((carpeta, trace, trace["meta"]["escenario"]))
    versiones = ", ".join(sorted({trace["schema_version"] for _, trace, _ in escenarios}))
    partes = ['<!doctype html><html lang="es"><head><meta charset="utf-8">',
              '<meta name="viewport" content="width=device-width,initial-scale=1">',
              f'<title>Harvest Sim · Dashboard</title><style>{CSS}</style></head><body>',
              '<header><div class="eyebrow">Equipo 3 / TC2008B / Coordinación multiagente</div>',
              '<h1>De la cosecha<br>a los resultados.</h1>',
              '<p>Explora el entorno, los indicadores y la comparación de estrategias de cosecha.</p>',
              f'<span class="badge">{len(escenarios)} escenarios · trace {versiones}</span>',
              '<nav aria-label="Paneles"><a href="#entorno">01 Entorno</a><a href="#indicadores">02 Indicadores</a><a href="#experimental">03 Experimental</a></nav></header><main>']
    if any(nombre.startswith(("ejemplo", "prueba")) for _, _, nombre in escenarios):
        partes.append('<p class="missing"><strong>Datos de ejemplo.</strong> Esta página sirve para verificar la interfaz; no presenta resultados de la simulación real.</p>')
    partes.append('<section id="entorno"><div class="section-head"><p class="eyebrow">01 / Reproducción</p><h2>Entorno</h2><p class="muted">Cuadros del visor: posición, orientación, carga y cosecha registrada en el log.</p></div>')
    for carpeta, trace, nombre in escenarios:
        partes.append(f'<article><h3>{escape(nombre)}</h3><p class="muted">Tick final: {escape(str(trace["meta"]["total_ticks"]))}. Desplaza horizontalmente los cuadros para recorrer la corrida.</p>')
        cuadros = sorted((carpeta / "cuadros").glob("tick_*.png"))
        if cuadros:
            partes.append(f'<div class="frames" tabindex="0" role="region" aria-label="Cuadros de {escape(nombre)}">')
            for cuadro in cuadros:
                partes.append(imagen(cuadro, f'{nombre} · {cuadro.stem.replace("_", " ")}', '¿Dónde están los agentes y qué celdas se han cosechado?'))
            partes.append('</div>')
        else:
            partes.append('<p class="missing">Sin cuadros. Genera PNG con viewer.py --guardar-cuadros en la carpeta cuadros de este escenario.</p>')
        partes.append('</article>')
    partes.append('</section><section id="indicadores"><div class="section-head"><p class="eyebrow">02 / Desempeño</p><h2>Indicadores</h2><p class="muted">Indicadores de cada corrida. Los datos ausentes se muestran como no disponibles.</p></div>')
    for carpeta, trace, nombre in escenarios:
        partes.append(f'<article><h3>{escape(nombre)}</h3><div class="metrics">')
        for clave, etiqueta, unidad in INDICADORES:
            valor = valor_metrica(trace.get("metricas", {}), clave)
            partes.append(f'<div class="metric"><span>{escape(etiqueta)}</span><strong>{escape(valor)}</strong><span>{escape(unidad)}</span></div>')
        partes.append('</div><div class="grid">')
        for archivo, titulo, pregunta in GRAFICAS[:4]:
            partes.append(imagen(carpeta / "plots" / archivo, titulo, pregunta))
        partes.append('</div></article>')
    partes.append('</section><section id="experimental"><div class="section-head"><p class="eyebrow">03 / Comparación</p><h2>Experimental</h2><p class="muted">Parámetros, resultados comparados y sensibilidad del sistema.</p></div><div class="card">')
    filas = []
    filas_avanzadas = []
    for _, trace, nombre in escenarios:
        cfg = trace["config"]
        politica = cfg.get("politica", {})
        combustible = cfg.get("combustible", {})
        incertidumbre = cfg.get("incertidumbre", {})
        rendimiento = incertidumbre.get("rendimiento", {})
        retraso = incertidumbre.get("retraso_mensajes", {})
        filas.append([nombre, f'{cfg.get("ancho", "—")} × {cfg.get("alto", "—")}',
                      *[cfg.get(k, "—") for k in ("num_cosechadoras", "num_carros", "grano_por_celda", "capacidad_cosechadora", "capacidad_carro", "tasa_transferencia", "tasa_descarga")],
                      len(trace["mundo"].get("obstaculos", [])), cfg.get("seed", "—"),
                      politica.get("asignacion", "—"), politica.get("umbral_aviso", "—"),
                      combustible.get("tanque_cosechadora", "—"), combustible.get("tanque_carro", "—")])
        opciones = [politica.get(k, "—") for k in ("atender_desde_bodega", "encadenar_servicios")]
        filas_avanzadas.append([nombre,
            *[("Sí" if v else "No") if isinstance(v, bool) else v for v in opciones],
            *[politica.get(k, "—") for k in ("espera_propuestas", "reintento_subasta")],
            rendimiento.get("minimo", "—"), rendimiento.get("maximo", "—"),
            incertidumbre.get("duracion_extra_maxima", "—"), retraso.get("probabilidad", "—"), retraso.get("maximo", "—"),
            combustible.get("reserva", "—"), combustible.get("tasa_recarga", "—")])
    partes.append(tabla("Parámetros por escenario", ["Escenario", "Campo (celdas)", "Cosechadoras", "Carros", "Grano (u./celda)", "Cap. cosechadora (u.)", "Cap. carro (u.)", "Transferencia (u./tick)", "Descarga (u./tick)", "Obstáculos", "Semilla", "Asignación", "Umbral de aviso", "Tanque cosechadora (L)", "Tanque carro (L)"], filas))
    partes.append(tabla("Política, incertidumbre y combustible", ["Escenario", "Atender desde bodega", "Encadenar servicios", "Espera de propuestas (ticks)", "Reintento de subasta (ticks)", "Rendimiento mínimo (u./celda)", "Rendimiento máximo (u./celda)", "Duración extra máxima (ticks)", "Probabilidad de retraso", "Retraso máximo (ticks)", "Reserva de combustible (fracción)", "Tasa de recarga (L/tick; 0 = instantánea)"], filas_avanzadas))
    partes.append(imagen(comparacion / "comparacion_escenarios.png", "Comparación entre escenarios", "¿Cómo cambian el tiempo, la distancia, la utilización y los bloqueos?"))
    partes.append('<details open><summary>Tabla resumen</summary>')
    partes.append(tabla_csv(comparacion / "resumen.csv", "Resultados comparados · unidades en los indicadores y gráficas"))
    partes.append('</details></div>')
    for carpeta, _, nombre in escenarios:
        partes.append(f'<article><h3>{escape(nombre)} · Distribución espacial</h3><div class="grid">')
        for archivo, titulo, pregunta in GRAFICAS[4:]:
            partes.append(imagen(carpeta / "plots" / archivo, titulo, pregunta))
        partes.append('</div></article>')
    partes.append('<article><h3>Sensibilidad de parámetros</h3>')
    graficas = sorted(experimentos.glob("*/sensibilidad_*.png"))
    if not graficas:
        partes.append('<p class="missing">Sin experimento generado. Este panel leerá las gráficas y el resumen del barrido cuando estén disponibles.</p>')
    for grafica in graficas:
        partes.append(imagen(grafica, f'{grafica.parent.name} · {grafica.stem}', '¿Cómo responde la métrica al variar este parámetro? Las unidades están indicadas en los ejes.'))
    for carpeta in sorted({g.parent for g in graficas}):
        partes.append('<details><summary>Resumen del experimento: ' + escape(carpeta.name) + '</summary>')
        partes.append(tabla_csv(carpeta / "resumen.csv", "Resumen estadístico del barrido"))
        partes.append('</details>')
    estrategias = experimentos / "estrategias"
    partes.append('<h3>Comparación por estrategia</h3><p class="muted">Gráficas con intervalos de confianza del 95 % y desglose del costo J, generados por el experimento.</p>')
    graficas_estrategia = sorted(estrategias.glob("*.png"))
    tablas_estrategia = [p for p in sorted(estrategias.glob("*.csv")) if p.stem.startswith(("resumen", "comparacion", "costo", "j_por"))]
    if not graficas_estrategia:
        partes.append('<p class="missing">Sin gráficas de comparación por estrategia.</p>')
    for grafica in graficas_estrategia:
        partes.append(imagen(grafica, grafica.stem.replace("_", " "), "¿Cómo cambia este resultado entre estrategias?"))
    if not tablas_estrategia:
        partes.append('<p class="missing">Sin tablas de resultados por estrategia o costo J.</p>')
    for resumen in tablas_estrategia:
        partes.append(tabla_csv(resumen, resumen.stem.replace("_", " ")))
    partes.append('</article></section></main><footer>Harvest Sim · Lectura de resultados guardados. La simulación es la única fuente de verdad. Tiempo en ticks, distancia en celdas y grano en unidades.</footer></body></html>')
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n".join(partes), encoding="utf-8")
    return salida


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("escenarios", nargs="+", type=Path)
    parser.add_argument("--salida", type=Path, default=Path("runs/dashboard.html"))
    parser.add_argument("--comparacion", type=Path, help="carpeta con comparación y resumen.csv")
    parser.add_argument("--experimentos", type=Path, help="carpeta que contiene los barridos")
    args = parser.parse_args(argv)
    try:
        salida = generar_dashboard(args.escenarios, args.salida, args.comparacion, args.experimentos)
        print(f"Dashboard: {salida}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
