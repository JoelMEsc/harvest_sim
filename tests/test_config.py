"""Configuración de escenarios.  [Bloque A]"""

import json
from pathlib import Path

import pytest

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
CAMPOS = {
    "nombre", "seed", "ancho", "alto", "num_carros", "num_cosechadoras",
    "grano_por_celda", "capacidad_cosechadora", "capacidad_carro",
    "tasa_transferencia", "tasa_descarga", "max_ticks", "obstaculos",
}


@pytest.mark.parametrize("nombre", ["escenario_a", "escenario_b", "escenario_c"])
def test_escenarios_tienen_todos_los_campos(nombre):
    """Humo: los JSON de escenario existen y traen exactamente los campos del §3."""
    datos = json.loads((CONFIG_DIR / f"{nombre}.json").read_text(encoding="utf-8"))
    assert set(datos) in (CAMPOS, CAMPOS - {"obstaculos"})
    assert datos["nombre"] == nombre


CONFIG_BASE = {
    "nombre": "escenario_test",
    "seed": 0,
    "ancho": 8,
    "alto": 7,
    "num_carros": 1,
    "num_cosechadoras": 1,
    "grano_por_celda": 1,
    "capacidad_cosechadora": 10,
    "capacidad_carro": 20,
    "tasa_transferencia": 2,
    "tasa_descarga": 4,
    "max_ticks": 5000,
    "obstaculos": {"celdas": [], "regiones": []},
}

CASOS_INVALIDOS = [
    # (descripcion, modificaciones, campo_a_eliminar, patron_error)
    ("capacidad_carro menor que cosechadora", {"capacidad_carro": 5, "capacidad_cosechadora": 10}, None, r"capacidad_carro"),
    ("capacidad cosechadora no múltiplo de grano", {"capacidad_cosechadora": 7, "grano_por_celda": 2}, None, r"múltiplo"),
    ("ancho insuficiente para bases", {"ancho": 2}, None, r"ancho"),
    ("alto menor a 2", {"alto": 1}, None, r"alto"),
    ("num_carros distinto de 1 no soportado", {"num_carros": 2}, None, r"aún no soportado"),
    ("num_cosechadoras distinto de 1 no soportado", {"num_cosechadoras": 2}, None, r"aún no soportado"),
    ("num_carros no positivo", {"num_carros": 0}, None, r"entero positivo"),
    ("num_cosechadoras no positivo", {"num_cosechadoras": 0}, None, r"entero positivo"),
    ("grano_por_celda no positivo", {"grano_por_celda": 0}, None, r"entero positivo"),
    ("tasa_transferencia no positiva", {"tasa_transferencia": 0}, None, r"entero positivo"),
    ("tasa_descarga negativa", {"tasa_descarga": -1}, None, r"entero positivo"),
    ("capacidad_cosechadora cero", {"capacidad_cosechadora": 0}, None, r"entero positivo"),
    ("capacidad_carro cero", {"capacidad_carro": 0}, None, r"entero positivo"),
    ("max_ticks cero", {"max_ticks": 0}, None, r"entero positivo"),
    ("obstáculos no vacíos no soportados", {"obstaculos": {"celdas": [[2, 2]], "regiones": []}}, None, r"aún no soportados"),
    ("obstáculos fuera del mapa", {"obstaculos": {"celdas": [[99, 99]], "regiones": []}}, None, r"fuera del mapa"),
    ("falta campo requerido", {}, "seed", r"falta seed"),
    ("campo desconocido", {"extra_parametro": 123}, None, r"desconocido"),
]


@pytest.mark.skip(reason="pendiente — espera config.py (Carlos)")
@pytest.mark.parametrize("desc,modificaciones,campo_borrar,patron", CASOS_INVALIDOS)
def test_config_invalida(tmp_path, desc, modificaciones, campo_borrar, patron):
    """Las validaciones del §3 fallan con mensaje claro: capacidad_carro < capacidad_cosechadora,
    capacidad no múltiplo de grano_por_celda, ancho < 1+n+m, alto < 2, num_* distinto de 1,
    tasas o cantidades no positivas."""
    from harvest_sim.config import cargar_config

    datos = dict(CONFIG_BASE)
    datos.update(modificaciones)
    if campo_borrar and campo_borrar in datos:
        del datos[campo_borrar]

    ruta = tmp_path / "invalido.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")

    with pytest.raises(ValueError, match=patron):
        cargar_config(ruta)
