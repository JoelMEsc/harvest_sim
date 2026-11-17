"""Armar, escribir, leer y verificar el trace.json (formato 2.1).  [Joel]

    builder = TraceBuilder(config, mundo, agentes)
    builder.agregar_tick(tick, registros, eventos)   # en TODOS los ticks, en orden
    trace = builder.construir(metricas)
    escribir_trace(trace, "runs/escenario_a/trace.json")
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .formato import CAMPOS_AGENTE, CATEGORIA, CLASE_AGENTE, CLASE_CELDAS, CLASE_REGISTRO, SCHEMA_VERSION

_AUSENTE = object()


def calcular_checksum(objeto: dict) -> str:
    """Primeros 16 caracteres hex de SHA-256 sobre el JSON canónico (claves ordenadas, sin
    espacios, ensure_ascii=False) del objeto SIN el campo `checksum`.

    Se usa por tick: el objeto es {"tick": t, "cambios": [...]}.
    """
    sin_checksum = {k: v for k, v in objeto.items() if k != "checksum"}
    canonico = json.dumps(sin_checksum, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()[:16]


def con_checksum(objeto: dict) -> dict:
    """Devuelve una copia del objeto con el campo `checksum` agregado al final."""
    return {**objeto, "checksum": calcular_checksum(objeto)}


def _con_clase(agente: dict) -> dict:
    """El agente del catálogo con `clase` justo después de `tipo` (la clase de la ontología es fija)."""
    salida = {}
    for clave, valor in agente.items():
        if clave != "clase":
            salida[clave] = copy.deepcopy(valor)
        if clave == "tipo":
            salida["clase"] = CLASE_AGENTE
    salida.setdefault("clase", CLASE_AGENTE)
    return salida


class TraceBuilder:
    """Arma el trace.json durante la simulación (la usa simulacion.ejecutar).

        TraceBuilder(config, mundo, agentes)
        builder.agregar_tick(tick, registros, eventos)   # en TODOS los ticks, en orden
        builder.construir(metricas=None) -> dict

    Las etiquetas de la ontología (`meta.clase`, `agentes[].clase`, `mundo.clase_celdas`) las agrega el
    builder: quien lo usa no tiene que escribirlas.
    """

    def __init__(self, config: dict, mundo: dict, agentes: list[dict]) -> None:
        """`config` = la configuración como dict; `mundo` = Mundo.descripcion() (ancho, alto, bodega,
        bases, grano_por_celda, obstaculos); `agentes` = catálogo estático (id, tipo, capacidad, base)."""
        self._config = copy.deepcopy(config)
        self._mundo = {k: copy.deepcopy(v) for k, v in mundo.items() if k != "clase_celdas"}
        if mundo:
            self._mundo["clase_celdas"] = CLASE_CELDAS
        self._agentes = [_con_clase(a) for a in agentes]
        self._ticks: list[dict] = []
        self._previo: dict[str, dict] = {}
        self._ultimo_tick: int | None = None

    def agregar_tick(self, tick: int, registros: list[dict], eventos: list[dict]) -> None:
        """Se llama en cada tick, con ticks estrictamente crecientes.

        - `registros`: Agente.registro() completos, SIN checksum, en el orden de los agentes.
        - `eventos`: los eventos del tick que no son AGENTE (celdas, depósitos, bloqueos, mensajes).
        Calcula los eventos AGENTE por diferencia con el tick anterior (solo los campos pose,
        estado y carga que cambian, cada campo completo), ordena todo por categoría, omite el tick
        si no hay cambios (salvo el 0) y le agrega el checksum.
        """
        if self._ultimo_tick is not None and tick <= self._ultimo_tick:
            raise ValueError(f"los ticks deben ser crecientes: {tick} después de {self._ultimo_tick}")

        for e in eventos:
            tipo = e.get("tipo")
            if tipo not in CATEGORIA or tipo == "AGENTE":
                raise ValueError(f"tipo de evento no válido en `eventos`: {tipo!r}")

        cambios_agentes = []
        for r in registros:
            actual = {
                "pose": copy.deepcopy(r["pose"]),
                "estado": r["estado"],
                "carga": r["carga"]["actual"],
            }
            previo = self._previo.get(r["agent_id"], {})
            nuevos = {c: actual[c] for c in CAMPOS_AGENTE if previo.get(c, _AUSENTE) != actual[c]}
            if nuevos:
                cambios_agentes.append({"tipo": "AGENTE", "id": r["agent_id"], "set": nuevos})
            self._previo[r["agent_id"]] = actual  # copia propia: el agente puede mutar su registro

        cambios = sorted(copy.deepcopy(eventos) + cambios_agentes, key=lambda e: CATEGORIA[e["tipo"]])
        if cambios or tick == 0:
            self._ticks.append(con_checksum({"tick": tick, "cambios": cambios}))
        self._ultimo_tick = tick

    def construir(self, metricas: dict | None = None) -> dict:
        """Devuelve el dict completo: schema_version, meta, config, mundo, agentes, ticks y
        metricas, en ese orden de inserción."""
        if self._ultimo_tick is None:
            raise ValueError("no hay ticks: llama a agregar_tick antes de construir")
        return {
            "schema_version": SCHEMA_VERSION,
            "meta": {
                "escenario": self._config.get("nombre"),
                "seed": self._config.get("seed"),
                "total_ticks": self._ultimo_tick,
                "clase": CLASE_REGISTRO,
            },
            "config": copy.deepcopy(self._config),
            "mundo": copy.deepcopy(self._mundo),
            "agentes": copy.deepcopy(self._agentes),
            "ticks": copy.deepcopy(self._ticks),
            "metricas": {} if metricas is None else copy.deepcopy(metricas),
        }


def cargar_trace(ruta: str | Path) -> dict:
    """Lee un trace.json."""
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def verificar_checksums(trace: dict) -> bool:
    """True si el checksum de cada tick coincide al recalcularlo."""
    return all(t.get("checksum") == calcular_checksum(t) for t in trace["ticks"])


def _legible(valor, nivel: int) -> str:
    """JSON con sangría de 2 espacios, pero las listas de valores simples ([x, y]) en una sola línea."""
    sangria, interior = "  " * nivel, "  " * (nivel + 1)
    if isinstance(valor, dict) and valor:
        filas = [f"{interior}{json.dumps(k, ensure_ascii=False)}: {_legible(v, nivel + 1)}" for k, v in valor.items()]
        return "{\n" + ",\n".join(filas) + "\n" + sangria + "}"
    if isinstance(valor, list) and any(isinstance(v, (dict, list)) for v in valor):
        return "[\n" + ",\n".join(interior + _legible(v, nivel + 1) for v in valor) + "\n" + sangria + "]"
    return json.dumps(valor, ensure_ascii=False)


def texto_del_trace(trace: dict) -> str:
    """El texto exacto que escribe `escribir_trace`.

    El primer nivel va con sangría (legible, con las coordenadas [x, y] en una línea) y cada tick en UNA
    línea (compacto: el archivo queda en cerca de la mitad o menos que con todo indentado). Orden de
    inserción fijo, sin sort_keys, ensure_ascii=False y salto de línea final: el mismo trace produce
    siempre los mismos bytes.
    """
    partes = []
    for clave, valor in trace.items():
        if clave == "ticks" and isinstance(valor, list) and valor:
            filas = ",\n".join("    " + json.dumps(t, ensure_ascii=False) for t in valor)
            texto = "[\n" + filas + "\n  ]"
        else:
            texto = _legible(valor, 1)
        partes.append(f"  {json.dumps(clave, ensure_ascii=False)}: {texto}")
    return "{\n" + ",\n".join(partes) + "\n}\n"


def escribir_trace(trace: dict, ruta: str | Path) -> None:
    """Escribe trace.json de forma reproducible byte a byte (ver `texto_del_trace`). Crea la carpeta."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto_del_trace(trace))
