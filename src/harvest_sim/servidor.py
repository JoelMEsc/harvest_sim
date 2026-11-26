"""Servidor FastAPI: corre simulaciones y entrega traces validados (especificación de la segunda entrega §14).  [Joel]

Python sigue siendo la única fuente de verdad: el servidor solo corre la simulación y entrega el trace.
Unity (y más adelante el visor WebGL) lo pide y lo reproduce; no decide nada.

Arrancar:
    uvicorn harvest_sim.servidor:app                          # simulación real
    HARVEST_SIMULADOR=ejemplo uvicorn harvest_sim.servidor:app # generador de ejemplo (1 + 1), para probar

Rutas:
    GET  /api/salud
    GET  /api/escenarios                                       # escenarios de config/ y estrategias (por escenario,
                                                               # las aprendidas solo si tienen tabla entrenada)
    GET  /api/escenarios/{nombre}/trace?seed=0&estrategia=base
    POST /api/simulaciones   {"config": {...}}  o  {"escenario", "estrategia", "seed", "cambios"}

Errores: 404 escenario desconocido; 422 configuración, estrategia o trace inválidos (con la lista de
errores); 503 si la simulación aún no está disponible.
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .aprendizaje import ruta_tabla
from .datos.experimentos import ESTRATEGIAS, ESTRATEGIAS_APRENDIDAS, aplicar_estrategia, simulador_real
from .datos.formato import SCHEMA_VERSION
from .datos.validacion import validar_trace

RAIZ = Path(__file__).resolve().parents[2]
TAMANO_CACHE = 64
# Orígenes locales (Editor de Unity no los necesita; el visor WebGL sí, en la entrega final).
ORIGENES_LOCALES = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"


class Simulacion(BaseModel):
    """Cuerpo de POST /api/simulaciones: una configuración completa, o un escenario con cambios."""
    config: dict | None = None
    escenario: str | None = None
    estrategia: str | None = None
    seed: int | None = Field(default=None, ge=0)
    cambios: dict = Field(default_factory=dict)


def simulador_ejemplo(config: dict) -> dict:
    """El generador de datos de ejemplo (1 cosechadora y 1 carro, sin obstáculos); no es la simulación."""
    import importlib.util

    ruta = RAIZ / "tools" / "generar_trace_ejemplo.py"
    spec = importlib.util.spec_from_file_location("generar_trace_ejemplo", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.generar(config)


def _parametros(config: dict) -> dict:
    claves = ("ancho", "alto", "num_cosechadoras", "num_carros", "capacidad_cosechadora", "capacidad_carro",
              "tasa_transferencia", "tasa_descarga", "seed")
    obstaculos = config.get("obstaculos") or {}
    return {**{c: config.get(c) for c in claves},
            "obstaculos": len(obstaculos.get("celdas", [])) + len(obstaculos.get("regiones", []))}


def crear_app(simulador: Callable[[dict], dict] | None = None, carpeta_config: str | Path | None = None,
              nombre_simulador: str | None = None) -> FastAPI:
    """Crea la aplicación. `simulador(config_dict) -> trace` es inyectable (pruebas y modo de ejemplo)."""
    if simulador is None:
        modo = os.environ.get("HARVEST_SIMULADOR", "real")
        simulador, nombre_simulador = (simulador_ejemplo, "ejemplo") if modo == "ejemplo" else (simulador_real, "real")
    carpeta = Path(carpeta_config) if carpeta_config else RAIZ / "config"
    cache: OrderedDict[str, dict] = OrderedDict()

    app = FastAPI(title="harvest_sim", version=SCHEMA_VERSION,
                  description="Corre simulaciones de harvest_sim y entrega traces validados.")
    app.add_middleware(CORSMiddleware, allow_origin_regex=ORIGENES_LOCALES, allow_methods=["GET", "POST"],
                       allow_headers=["*"])

    def escenarios() -> dict[str, dict]:
        return {ruta.stem: json.loads(ruta.read_text(encoding="utf-8"))
                for ruta in sorted(carpeta.glob("escenario_*.json"))}

    def correr(config: dict) -> dict:
        clave = json.dumps(config, sort_keys=True, ensure_ascii=False)
        if clave in cache:
            cache.move_to_end(clave)
            return cache[clave]
        try:
            trace = simulador(config)
        except NotImplementedError as exc:
            raise HTTPException(503, f"la simulación aún no está disponible: {exc}") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, {"mensaje": "configuración inválida", "errores": [str(exc)]}) from exc
        errores = validar_trace(trace)
        if errores:
            raise HTTPException(422, {"mensaje": "el trace generado no es válido", "errores": errores[:50]})
        cache[clave] = trace
        if len(cache) > TAMANO_CACHE:
            cache.popitem(last=False)
        return trace

    def config_de(escenario: str, estrategia: str | None, seed: int | None, cambios: dict) -> dict:
        todos = escenarios()
        if escenario not in todos:
            raise HTTPException(404, f"escenario {escenario!r} no existe; hay: {list(todos)}")
        config = {**todos[escenario], **cambios}
        if estrategia is not None:
            try:
                config = aplicar_estrategia(config, estrategia)
            except ValueError as exc:
                raise HTTPException(422, {"mensaje": "estrategia inválida", "errores": [str(exc)]}) from exc
        if seed is not None:
            config["seed"] = seed
        return config

    @app.get("/api/salud")
    def salud() -> dict:
        return {"estado": "ok", "schema_version": SCHEMA_VERSION, "simulador": nombre_simulador or "personalizado"}

    def estrategias_de(nombre: str, config: dict) -> list[str]:
        """Las 4 de coordinación siempre; las aprendidas (M1) solo si el escenario tiene su tabla entrenada."""
        politica = config.get("politica") or {}
        aprendidas = [e for e in ESTRATEGIAS_APRENDIDAS
                      if ruta_tabla({**politica, "aviso": e, "qtabla": None}, config.get("nombre", nombre)).is_file()]
        return list(ESTRATEGIAS) + aprendidas

    @app.get("/api/escenarios")
    def listar() -> dict:
        todos = escenarios()
        return {"escenarios": [{"nombre": n, "parametros": _parametros(c), "estrategias": estrategias_de(n, c)}
                               for n, c in todos.items()],
                "estrategias": list(ESTRATEGIAS) + list(ESTRATEGIAS_APRENDIDAS)}

    @app.get("/api/escenarios/{nombre}/trace")
    def trace_de_escenario(nombre: str, seed: int | None = Query(default=None, ge=0),
                           estrategia: str | None = None) -> dict:
        return correr(config_de(nombre, estrategia, seed, {}))

    @app.post("/api/simulaciones")
    def simular(cuerpo: Simulacion) -> dict:
        if cuerpo.config is not None:
            config = dict(cuerpo.config)
            if cuerpo.estrategia is not None:
                try:
                    config = aplicar_estrategia(config, cuerpo.estrategia)
                except ValueError as exc:
                    raise HTTPException(422, {"mensaje": "estrategia inválida", "errores": [str(exc)]}) from exc
            if cuerpo.seed is not None:
                config["seed"] = cuerpo.seed
            return correr(config)
        if cuerpo.escenario is None:
            raise HTTPException(422, {"mensaje": "falta config o escenario", "errores": []})
        return correr(config_de(cuerpo.escenario, cuerpo.estrategia, cuerpo.seed, cuerpo.cambios))

    return app


app = crear_app()
