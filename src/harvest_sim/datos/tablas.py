"""Utilidades para tablas.  [Joel]"""

from __future__ import annotations


def aplanar_metricas(metricas: dict, prefijo: str = "") -> dict:
    """{'a': {'b': 1}, 'l': [1, 2]} -> {'a.b': 1, 'l': '1;2'}: una columna por valor, para tablas y comparaciones.

    Con las métricas, `por_agente` queda como columnas `por_agente.<id>.<métrica>`.
    """
    plano = {}
    for clave, valor in metricas.items():
        nombre = f"{prefijo}.{clave}" if prefijo else clave
        if isinstance(valor, dict):
            plano.update(aplanar_metricas(valor, nombre))
        elif isinstance(valor, list):
            plano[nombre] = ";".join(str(v) for v in valor)
        else:
            plano[nombre] = valor
    return plano
