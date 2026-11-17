"""Gráficas y tabla comparativa a partir de trace.json.  [Joel]

Solo lee el log: usa `harvest_sim.datos` (línea de tiempo, métricas y series), nunca la simulación. Cada
trace se recorre UNA vez (`linea_de_tiempo`) y todas las gráficas y la tabla leen de esa línea de tiempo.
Funciona con cualquier número de agentes: por defecto muestra promedios entre cosechadoras; con
`--agente <id>` las gráficas 2 y 3 muestran solo esa cosechadora.

Uso:
    python viz/plots.py runs/escenario_a/trace.json
    python viz/plots.py runs/escenario_a/trace.json runs/escenario_b/trace.json runs/escenario_c/trace.json
    python viz/plots.py runs/escenario_a/trace.json --agente cosechadora_1

Gráficas de cada corrida (en <carpeta del trace>/plots/), una pregunta cada una:
  1. Línea de tiempo de estados (una fila por agente).         ¿Qué hace cada agente en cada momento?
  2. Tiempo ocioso acumulado (promedio por cosechadora).       ¿Cuánto ha esperado hasta ahora?
  3. Distancia cosechadora–carro más cercano (promedio).        ¿Qué tan lejos está el carro?
  4. Flujo del grano: en la bodega + en tránsito = cosechado.   ¿Cuánto grano llega y cuánto va en camino?
  5. Mapa de calor de la espera por celda.                      ¿Dónde espera la cosechadora?
  6. Mapa de calor del tráfico por celda.                       ¿Por dónde pasan los agentes?
Entre escenarios (en <runs>/comparacion/): comparacion_escenarios.png (6 indicadores) y la tabla resumen
(resumen.csv con todas las métricas, resumen.md con las principales).
Experimentos: grafica_sensibilidad (una métrica contra un parámetro, una línea por escenario).

Diseño (guía de visualización): paleta categórica validada con 6 hues en orden fijo, rampa secuencial azul
para los mapas, texto en tintas de texto (nunca en el color de la serie), marcas delgadas con un hueco del
color de la superficie entre ellas, leyenda cuando hay 2 o más series. Los 11 estados se agrupan en 7
categorías de actividad para no pasar de la paleta validada.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin ventana: funciona en servidores y en CI
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))  # permite correrlo sin instalar el paquete (pip install -e .)

from harvest_sim.datos import (  # noqa: E402
    aplanar_metricas,
    calcular_metricas,
    cargar_trace,
    grano_esperado,
    linea_de_tiempo,
    mapa_por_celda,
    obstaculos,
    series_temporales,
)
from harvest_sim.datos.formato import (  # noqa: E402
    COSECHANDO,
    COSECHADORA,
    DESCARGANDO,
    EN_BASE,
    ESPERANDO_TRANSFERENCIA,
    FIN,
    LLENA_ESPERANDO,
    REGRESANDO_A_BASE,
    TRANSFIRIENDO,
    YENDO_A_BODEGA,
    YENDO_A_CAMPO,
    YENDO_A_COSECHADORA,
)

# --- Tokens de la paleta de referencia (modo claro) ---------------------------------------------
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TINTA_TENUE = "#898781"
REJILLA = "#e1e0d9"
EJE = "#c3c2b7"
NEUTRO = "#f0efec"  # "nada" en los mapas (celda con 0)
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, VERDE = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"
# Orden fijo de los hues categóricos (el orden validado): azul, naranja, aqua, amarillo, magenta, verde
SERIES = [AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, VERDE]
# Rampa secuencial azul (pasos 100 a 700) para magnitudes en los mapas de calor
RAMPA_AZUL = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
              "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]

# Categorías de actividad: (clave, etiqueta de la leyenda, color, estados). El color sigue a la categoría.
CATEGORIAS = [
    ("desplazamiento", "Desplazamiento", AZUL, {YENDO_A_CAMPO, YENDO_A_COSECHADORA, YENDO_A_BODEGA, REGRESANDO_A_BASE}),
    ("ocioso", "Cosechadora llena esperando al carro (ocioso)", NARANJA, {LLENA_ESPERANDO}),
    ("cosecha", "Cosechando", AQUA, {COSECHANDO}),
    ("espera_carro", "Carro esperando la transferencia", AMARILLO, {ESPERANDO_TRANSFERENCIA}),
    ("transferencia", "Transfiriendo", MAGENTA, {TRANSFIRIENDO}),
    ("descarga", "Descargando en la bodega", VERDE, {DESCARGANDO}),
    ("reposo", "En base o terminado", EJE, {EN_BASE, FIN}),
]
OTROS = ("otros", "Otros estados", TINTA_TENUE)
CATEGORIA_DE_ESTADO = {estado: (clave, etiqueta, color) for clave, etiqueta, color, estados in CATEGORIAS for estado in estados}

# Paneles de la comparación: (métrica, título). Cada una responde algo distinto; las demás van en la tabla.
METRICAS_COMPARACION = [
    ("tiempo_completacion", "Tiempo de completación\n(ticks)"),
    ("tiempo_ocioso_cosechadora", "Tiempo ocioso por cosechadora\n(ticks, promedio)"),
    ("distancia_total", "Distancia recorrida total\n(celdas)"),
    ("distancia_cosechadora_carro_promedio", "Distancia media cosechadora–carro\n(celdas)"),
    ("utilizacion_carro", "Utilización del carro\n(fracción del tiempo, promedio)"),
    ("ticks_bloqueados", "Bloqueos\n(eventos, total)"),
]
# Columnas de la tabla en Markdown (el CSV lleva todas las métricas)
COLUMNAS_MD = [
    ("escenario", "Escenario"),
    ("agentes", "Agentes (cosechadoras + carros)"),
    ("tiempo_completacion", "Tiempo de completación"),
    ("tiempo_ocioso_cosechadora", "Tiempo ocioso"),
    ("porcentaje_ocioso", "% ocioso"),
    ("espera_promedio_por_ciclo", "Espera media por ciclo"),
    ("distancia_total", "Distancia total"),
    ("distancia_cosechadora_carro_promedio", "Distancia media cosechadora–carro"),
    ("utilizacion_carro", "Utilización del carro"),
    ("ticks_bloqueados", "Bloqueos"),
    ("colisiones", "Colisiones"),
    ("num_ciclos", "Ciclos"),
    ("porcentaje_entregado", "% entregado"),
]
NOMBRES_GRAFICAS = ["1_linea_de_tiempo_estados.png", "2_ocioso_acumulado.png", "3_distancia_cosechadora_carro.png",
                    "4_flujo_del_grano.png", "5_mapa_espera.png", "6_mapa_trafico.png"]


def _estilo():
    plt.rcParams.update({
        "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
        "axes.edgecolor": EJE, "axes.labelcolor": TINTA_2, "axes.titlecolor": TINTA,
        "xtick.color": TINTA_2, "ytick.color": TINTA_2, "text.color": TINTA,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": REJILLA, "grid.linewidth": 1, "grid.linestyle": "-",
        "axes.axisbelow": True, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "legend.frameon": False, "legend.fontsize": 9,
    })


def nombre_escenario(trace, ruta=None):
    return trace["meta"].get("escenario") or (Path(ruta).resolve().parent.name if ruta else "escenario")


def _guardar(fig, destino):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150, bbox_inches="tight", pad_inches=0.25, metadata={"Software": None})
    plt.close(fig)
    return destino


def _categoria(estado):
    return CATEGORIA_DE_ESTADO.get(estado, OTROS)


def _color_texto(color):
    return TINTA if color in (AMARILLO, EJE) else "#ffffff"


def _formato(valor):
    return "—" if valor is None else f"{valor:g}"


def _formato_corto(valor):
    """Para etiquetas sobre las barras: hasta 2 decimales."""
    return "—" if valor is None else f"{round(valor, 2):g}"


def _revisar_agente(linea, agente):
    if agente is not None and agente not in linea.ids(COSECHADORA):
        raise ValueError(f"--agente {agente!r} no es una cosechadora del trace (hay: {linea.ids(COSECHADORA)})")


def _de_quien(linea, agente):
    n = len(linea.ids(COSECHADORA))
    return agente if agente else ("la cosechadora" if n == 1 else f"promedio de {n} cosechadoras")


def _tramos(estados):
    """[(estado, tick_inicial, largo)] con ticks consecutivos del mismo estado."""
    tramos = []
    for t, estado in enumerate(estados):
        if tramos and tramos[-1][0] == estado:
            tramos[-1][2] += 1
        else:
            tramos.append([estado, t, 1])
    return tramos


# --- 1. Línea de tiempo de estados --------------------------------------------------------------
def grafica_estados(trace, destino, ruta=None, linea=None):
    _estilo()
    linea = linea or linea_de_tiempo(trace)
    total = linea.num_ticks
    agentes = linea.ids()
    ancho_fig = 13
    ticks_por_pulgada = total / (ancho_fig * 0.82)
    fig, ax = plt.subplots(figsize=(ancho_fig, 1.5 + 0.9 * len(agentes)))
    ax.grid(axis="y", visible=False)
    presentes = {}
    for fila, a in enumerate(agentes):
        y = len(agentes) - 1 - fila
        for estado, inicio, largo in _tramos(linea.estado[a]):
            clave, etiqueta, color = _categoria(estado)
            presentes.setdefault(clave, (etiqueta, color))
            ax.barh(y, largo, left=inicio, height=0.5, color=color, edgecolor=SUPERFICIE, linewidth=1.5)
            if estado and largo / ticks_por_pulgada >= 0.065 * len(estado) + 0.05:  # el nombre cabe en la barra
                ax.text(inicio + largo / 2, y, estado, ha="center", va="center", fontsize=7, color=_color_texto(color))
    ax.set_yticks(range(len(agentes)))
    ax.set_yticklabels(list(reversed(agentes)))
    ax.set_xlim(0, total)
    ax.set_ylim(-0.6, len(agentes) - 0.4)
    ax.set_xlabel("Tick")
    ax.set_title(f"Línea de tiempo de estados — {nombre_escenario(trace, ruta)}")
    orden = [c for c in CATEGORIAS if c[0] in presentes] + ([OTROS] if "otros" in presentes else [])
    asas = [Patch(facecolor=c[2], edgecolor=SUPERFICIE, label=c[1]) for c in orden]
    ax.legend(handles=asas, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=min(4, len(asas)))
    return _guardar(fig, destino)


# --- 2. Tiempo ocioso acumulado -----------------------------------------------------------------
def grafica_ocioso_acumulado(trace, destino, ruta=None, linea=None, series=None, agente=None):
    """Curva continua: plana mientras la cosechadora trabaja y con pendiente 1 mientras espera al carro.
    Cada punto marca el fin de una espera y su valor es el total acumulado hasta ese momento. Con varias
    cosechadoras es el promedio (pendiente = fracción de cosechadoras esperando)."""
    _estilo()
    linea = linea or linea_de_tiempo(trace)
    _revisar_agente(linea, agente)
    s = series or series_temporales(linea)
    ticks = s["tick"]
    acumulado = [v or 0 for v in (s["por_agente"][agente]["ocioso_acumulado"] if agente else s["ocioso_acumulado"])]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(ticks, acumulado, color=NARANJA, linewidth=2, solid_capstyle="round", solid_joinstyle="round", zorder=3)
    finales = [t for t in ticks if t > 0 and acumulado[t] > acumulado[t - 1]
               and (t == ticks[-1] or acumulado[t + 1] == acumulado[t])]
    ax.plot(finales, [acumulado[t] for t in finales], linestyle="none", marker="o", markersize=8,
            color=NARANJA, markeredgecolor=SUPERFICIE, markeredgewidth=2, zorder=4)
    for t in finales:
        ax.annotate(_formato(acumulado[t]), (t, acumulado[t]), xytext=(0, 9), textcoords="offset points",
                    ha="center", color=TINTA_2, fontsize=9)
    ax.set_title(f"Tiempo ocioso acumulado ({_de_quien(linea, agente)}) — {nombre_escenario(trace, ruta)}")
    ax.set_xlabel("Tick")
    ax.set_ylabel("Ticks acumulados esperando al carro")
    ax.set_xlim(0, ticks[-1] or 1)
    ax.set_ylim(0, max(acumulado + [1]) * 1.18)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    return _guardar(fig, destino)


# --- 3. Distancia entre la cosechadora y el carro más cercano ------------------------------------
def grafica_distancia(trace, destino, ruta=None, linea=None, series=None, agente=None):
    _estilo()
    linea = linea or linea_de_tiempo(trace)
    _revisar_agente(linea, agente)
    s = series or series_temporales(linea)
    ticks = s["tick"]
    distancia = s["por_agente"][agente]["distancia_al_carro"] if agente else s["distancia_cosechadora_carro"]
    valores = [d for d in distancia if d is not None]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    if valores:
        promedio = sum(valores) / len(valores)
        ax.axhline(promedio, color=TINTA_TENUE, linewidth=1, zorder=1)
        ax.text(0.99, 0.96, f"línea gris: promedio ({promedio:.1f} celdas)", transform=ax.transAxes, ha="right",
                va="top", color=TINTA_2, fontsize=9)
        ax.step(ticks, [d if d is not None else float("nan") for d in distancia], where="post", color=AZUL,
                linewidth=2, solid_capstyle="round", solid_joinstyle="round", zorder=3)
    ax.set_title(f"Distancia al carro más cercano ({_de_quien(linea, agente)}) — {nombre_escenario(trace, ruta)}")
    ax.set_xlabel("Tick")
    ax.set_ylabel("Distancia (celdas, Manhattan)")
    ax.set_xlim(0, ticks[-1] or 1)
    ax.set_ylim(0, max(valores + [1]) * 1.15)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    return _guardar(fig, destino)


# --- 4. Flujo del grano -------------------------------------------------------------------------
def grafica_flujo_grano(trace, destino, ruta=None, linea=None, series=None):
    """Áreas apiladas: en la bodega (abajo) + en tránsito en los agentes (arriba) = cosechado acumulado.
    La línea gris es el total esperado del campo (campo.grano_esperado, descuenta obstáculos)."""
    _estilo()
    linea = linea or linea_de_tiempo(trace)
    s = series or series_temporales(linea)
    ticks, bodega, transito = s["tick"], s["entregado_en_bodega"], s["en_transito"]
    tope = [b + t for b, t in zip(bodega, transito)]
    esperado = grano_esperado(linea.mundo)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    if esperado:
        ax.axhline(esperado, color=TINTA_TENUE, linewidth=1, zorder=1)
        ax.text(0.01, esperado, f"total esperado ({esperado})", transform=ax.get_yaxis_transform(), ha="left",
                va="bottom", color=TINTA_2, fontsize=9)
    ax.fill_between(ticks, 0, bodega, step="post", color=AZUL, linewidth=0, zorder=3, label="En la bodega")
    ax.fill_between(ticks, bodega, tope, step="post", color=AQUA, linewidth=0, zorder=3,
                    label="En tránsito (en los agentes)")
    ax.step(ticks, bodega, where="post", color=SUPERFICIE, linewidth=1.5, zorder=4)  # hueco entre las áreas
    ax.set_title(f"Flujo del grano: cosechado = en tránsito + en la bodega — {nombre_escenario(trace, ruta)}")
    ax.set_xlabel("Tick")
    ax.set_ylabel("Unidades de grano")
    ax.set_xlim(0, ticks[-1] or 1)
    ax.set_ylim(0, (esperado or max(tope + [1])) * 1.15)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
    return _guardar(fig, destino)


# --- 5 y 6. Mapas de calor por celda ------------------------------------------------------------
TITULOS_MAPA = {
    "espera": ("Dónde espera la cosechadora llena", "Ticks esperando"),
    "trafico": ("Por dónde pasan los agentes", "Entradas a la celda"),
}


def grafica_mapa(trace, destino, criterio, ruta=None, linea=None):
    """Una celda por casilla del mapa (y = 0 arriba, como en el visor). Rampa secuencial azul; las celdas en 0
    van en gris neutro; la bodega y las bases llevan su etiqueta y los obstáculos una ×."""
    _estilo()
    linea = linea or linea_de_tiempo(trace)
    mapa = mapa_por_celda(linea, criterio)
    alto, ancho = len(mapa), len(mapa[0])
    maximo = max(max(f) for f in mapa) or 1
    rampa = LinearSegmentedColormap.from_list("azul", RAMPA_AZUL)
    lado = min(0.6, 9 / max(ancho, alto))
    fig, ax = plt.subplots(figsize=(max(5.5, ancho * lado + 2), max(3.5, alto * lado + 1.5)))
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    con_obstaculo = obstaculos(linea.mundo)
    etiquetas = {}
    if linea.mundo.get("bodega"):
        etiquetas[tuple(linea.mundo["bodega"])] = "bodega"
    tipo_de = {a["id"]: a.get("tipo") for a in linea.agentes}
    for a, base in (linea.mundo.get("bases") or {}).items():  # "base H1" (cosechadora 1), "base C1" (carro 1)
        inicial = {COSECHADORA: "H", "carro": "C"}.get(tipo_de.get(a))
        etiquetas[tuple(base)] = f"base {inicial}{a.split('_')[-1]}" if inicial else f"base {a}"
    numeros = ancho <= 20 and alto <= 20
    for y in range(alto):
        for x in range(ancho):
            v = mapa[y][x]
            if (x, y) in con_obstaculo:
                color = TINTA_2
            else:
                color = NEUTRO if v == 0 else rampa(v / maximo)
            ax.add_patch(Rectangle((x, y), 1, 1, facecolor=color, edgecolor=SUPERFICIE, linewidth=2))
            if (x, y) in con_obstaculo:
                ax.text(x + 0.5, y + 0.5, "×", ha="center", va="center", color="#ffffff", fontsize=11)
                continue
            texto = []
            if numeros and v:
                texto.append(str(v))
            if (x, y) in etiquetas:
                texto.append(etiquetas[(x, y)])
            if texto:
                claro = v == 0 or v / maximo < 0.55
                ax.text(x + 0.5, y + 0.5, "\n".join(texto), ha="center", va="center", fontsize=7,
                        color=TINTA if claro else "#ffffff")
    ax.set_xlim(0, ancho)
    ax.set_ylim(alto, 0)
    ax.set_aspect("equal")
    ax.set_xticks([x + 0.5 for x in range(ancho)])
    ax.set_xticklabels(range(ancho), fontsize=8)
    ax.set_yticks([y + 0.5 for y in range(alto)])
    ax.set_yticklabels(range(alto), fontsize=8)
    ax.tick_params(length=0)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    titulo, unidad = TITULOS_MAPA[criterio]
    ax.set_title(f"{titulo} — {nombre_escenario(trace, ruta)}")
    barra = fig.colorbar(plt.cm.ScalarMappable(cmap=rampa, norm=plt.Normalize(0, maximo)), ax=ax, shrink=0.8)
    barra.set_label(unidad + " (gris = 0)", color=TINTA_2)
    barra.outline.set_visible(False)
    return _guardar(fig, destino)


# --- Comparación entre escenarios ---------------------------------------------------------------
def _etiqueta_escenario(n):
    return n.replace("escenario_", "").upper() if n.startswith("escenario_") else n


def grafica_comparacion(traces, destino, metricas=None):
    """`traces`: {nombre: trace}. Un panel por indicador (cada uno con su propia escala) y un color fijo
    por escenario. `metricas`: {nombre: métricas} ya calculadas (opcional, para no recalcularlas)."""
    if len(traces) > len(SERIES):
        raise ValueError(f"se pueden comparar hasta {len(SERIES)} escenarios a la vez")
    _estilo()
    metricas = metricas or {nombre: calcular_metricas(t) for nombre, t in traces.items()}
    nombres = list(traces)
    columnas = 3
    filas = -(-len(METRICAS_COMPARACION) // columnas)
    fig, ejes = plt.subplots(filas, columnas, figsize=(12, 3.9 * filas))
    for ax, (clave, titulo) in zip(ejes.flat, METRICAS_COMPARACION):
        valores = [metricas[n][clave] or 0 for n in nombres]
        barras = ax.bar(range(len(nombres)), valores, width=0.55, color=SERIES[:len(nombres)],
                        edgecolor=SUPERFICIE, linewidth=1.5)
        for barra, valor in zip(barras, valores):
            ax.text(barra.get_x() + barra.get_width() / 2, valor, _formato_corto(valor), ha="center", va="bottom",
                    color=TINTA_2, fontsize=9)
        ax.set_title(titulo, fontsize=10)
        ax.set_xticks(range(len(nombres)))
        ax.set_xticklabels([_etiqueta_escenario(n) for n in nombres], fontsize=9)
        ax.grid(axis="x", visible=False)
        ax.set_xlim(-0.7, max(len(nombres), 3) - 1 + 0.7)
        ax.set_ylim(0, max(valores + [0]) * 1.18 or 1)
    for ax in list(ejes.flat)[len(METRICAS_COMPARACION):]:
        ax.set_visible(False)
    if len(nombres) > 1:
        asas = [Patch(facecolor=SERIES[i], edgecolor=SUPERFICIE, label=n) for i, n in enumerate(nombres)]
        fig.legend(handles=asas, loc="lower center", ncol=len(asas))
    fig.suptitle("Comparación entre escenarios (línea base)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout(rect=(0, 0.05 if len(nombres) > 1 else 0, 1, 0.96))
    return _guardar(fig, destino)


# --- Tabla resumen ------------------------------------------------------------------------------
def tabla_resumen(traces, destino_csv, destino_md, metricas=None):
    """Una fila por escenario. El CSV lleva TODAS las métricas (anidadas aplanadas con '.', incluido el
    detalle por agente); el Markdown, las principales."""
    metricas = metricas or {nombre: calcular_metricas(t) for nombre, t in traces.items()}
    destino_csv, destino_md = Path(destino_csv), Path(destino_md)
    destino_csv.parent.mkdir(parents=True, exist_ok=True)

    filas = {nombre: {"escenario": nombre, **aplanar_metricas(m)} for nombre, m in metricas.items()}
    columnas = []
    for fila in filas.values():
        columnas += [c for c in fila if c not in columnas]  # unión, en orden de aparición
    with open(destino_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columnas)
        for fila in filas.values():
            w.writerow(["" if fila.get(c) is None else fila.get(c, "") for c in columnas])

    def valor_md(nombre, clave):
        if clave == "escenario":
            return nombre
        v = metricas[nombre].get(clave)
        if clave == "agentes":
            return f"{v['cosechadoras']} + {v['carros']}"
        return _formato(v)

    lineas = ["| " + " | ".join(t for _, t in COLUMNAS_MD) + " |", "|" + "---|" * len(COLUMNAS_MD)]
    for nombre in metricas:
        lineas.append("| " + " | ".join(valor_md(nombre, k) for k, _ in COLUMNAS_MD) + " |")
    destino_md.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return destino_csv, destino_md


# --- Sensibilidad (experimentos) ----------------------------------------------------------------
def grafica_sensibilidad(resumen, parametro, metrica, destino, titulo_metrica=None):
    """`resumen`: filas de datos.experimentos.resumen_por_grupo. Una línea por escenario: la media de
    `metrica` contra los valores de `parametro`, con su intervalo de confianza del 95 % (si hay variación)."""
    _estilo()
    escenarios = list(dict.fromkeys(f["escenario"] for f in resumen))
    if len(escenarios) > len(SERIES):
        raise ValueError(f"se pueden graficar hasta {len(SERIES)} escenarios a la vez")
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for i, e in enumerate(escenarios):
        filas = sorted((f for f in resumen if f["escenario"] == e and f.get(f"{metrica}_media") is not None),
                       key=lambda f: f[parametro])
        xs = [f[parametro] for f in filas]
        ys = [f[f"{metrica}_media"] for f in filas]
        ic = [f.get(f"{metrica}_ic95") or 0 for f in filas]
        if any(ic):
            ax.fill_between(xs, [y - d for y, d in zip(ys, ic)], [y + d for y, d in zip(ys, ic)], color=SERIES[i],
                            alpha=0.15, linewidth=0)
        ax.plot(xs, ys, color=SERIES[i], linewidth=2, marker="o", markersize=8, markeredgecolor=SUPERFICIE,
                markeredgewidth=2, label=e)
        if len(escenarios) <= 4 and xs:
            ax.annotate(e, (xs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points", va="center",
                        color=TINTA_2, fontsize=9)
    nombre_metrica = titulo_metrica or metrica.replace("_", " ")
    ax.set_title(f"Sensibilidad: {nombre_metrica} según {parametro.replace('_', ' ')}")
    ax.set_xlabel(parametro.replace("_", " "))
    ax.set_ylabel(nombre_metrica)
    ax.set_ylim(bottom=0)
    if len(escenarios) > 1:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=min(len(escenarios), 6))
    return _guardar(fig, destino)


# --- Orquestación -------------------------------------------------------------------------------
def graficas_de_un_trace(ruta_trace, carpeta=None, agente=None, trace=None):
    """Las 6 gráficas de un trace.json, con una sola pasada por el trace. Devuelve las rutas generadas."""
    trace = trace or cargar_trace(ruta_trace)
    carpeta = Path(carpeta) if carpeta else Path(ruta_trace).resolve().parent / "plots"
    linea = linea_de_tiempo(trace)
    _revisar_agente(linea, agente)
    s = series_temporales(linea)
    n = dict(zip(range(1, 7), NOMBRES_GRAFICAS))
    return [
        grafica_estados(trace, carpeta / n[1], ruta_trace, linea),
        grafica_ocioso_acumulado(trace, carpeta / n[2], ruta_trace, linea, s, agente),
        grafica_distancia(trace, carpeta / n[3], ruta_trace, linea, s, agente),
        grafica_flujo_grano(trace, carpeta / n[4], ruta_trace, linea, s),
        grafica_mapa(trace, carpeta / n[5], "espera", ruta_trace, linea),
        grafica_mapa(trace, carpeta / n[6], "trafico", ruta_trace, linea),
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Genera las gráficas y la tabla resumen a partir de trace.json.")
    parser.add_argument("trace", nargs="+", help="uno o más trace.json (la comparación y la tabla juntan varios)")
    parser.add_argument("--salida", help="carpeta de salida (por defecto, junto a cada trace y en <runs>/comparacion)")
    parser.add_argument("--agente", help="id de una cosechadora: las gráficas 2 y 3 muestran solo esa (no el promedio)")
    args = parser.parse_args(argv)

    traces, metricas, generados = {}, {}, []
    try:
        for ruta in args.trace:
            trace = cargar_trace(ruta)
            nombre = nombre_escenario(trace, ruta)
            traces[nombre] = trace
            metricas[nombre] = calcular_metricas(linea_de_tiempo(trace))
            carpeta = Path(args.salida) / nombre if args.salida else None
            generados += graficas_de_un_trace(ruta, carpeta, args.agente, trace)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.salida:
        comparacion = Path(args.salida) / "comparacion"
    else:
        comparacion = Path(args.trace[0]).resolve().parent.parent / "comparacion"
    generados.append(grafica_comparacion(traces, comparacion / "comparacion_escenarios.png", metricas))
    generados += tabla_resumen(traces, comparacion / "resumen.csv", comparacion / "resumen.md", metricas)
    for g in generados:
        print(g)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
