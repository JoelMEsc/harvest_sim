"""Datos: el log (trace.json), su validación, las métricas y los experimentos.  [Joel]

Un módulo por responsabilidad:

    formato.py          versión del esquema, tipos de evento, vocabulario (estados, mensajes) y clases de la ontología
    trace.py            TraceBuilder (arma el log), checksum, escribir / cargar / verificar
    linea_de_tiempo.py  una sola pasada por el trace: estado de cada tick (y `reconstruir`)
    campo.py            celdas de campo, obstáculos y grano esperado (la fórmula en un solo lugar)
    metricas.py         métricas (promedio por tipo de agente + detalle por agente), series y mapas por celda
    validacion.py       validar_trace: el contrato del formato, ejecutable
    experimentos.py     escenarios x barrido de parámetros x repeticiones, con resumen estadístico
    tablas.py           aplanar_metricas (para CSV)

`harvest_sim.telemetria` reexporta lo mismo (compatibilidad con los imports del equipo).
"""

from .campo import celdas_de_campo, expandir_obstaculos, grano_esperado, obstaculos
from .formato import PERFORMATIVAS, SCHEMA_VERSION
from .linea_de_tiempo import LineaDeTiempo, linea_de_tiempo, reconstruir
from .metricas import calcular_metricas, distancias_al_carro, mapa_por_celda, series_temporales
from .tablas import aplanar_metricas
from .trace import (
    TraceBuilder,
    calcular_checksum,
    cargar_trace,
    con_checksum,
    escribir_trace,
    texto_del_trace,
    verificar_checksums,
)
from .validacion import validar_trace

__all__ = [
    "SCHEMA_VERSION", "PERFORMATIVAS",
    "TraceBuilder", "calcular_checksum", "con_checksum", "cargar_trace", "escribir_trace", "texto_del_trace",
    "verificar_checksums",
    "LineaDeTiempo", "linea_de_tiempo", "reconstruir",
    "celdas_de_campo", "expandir_obstaculos", "grano_esperado", "obstaculos",
    "calcular_metricas", "distancias_al_carro", "mapa_por_celda", "series_temporales",
    "validar_trace", "aplanar_metricas",
]
