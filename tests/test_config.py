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
    """Humo: los JSON de escenario existen y traen exactamente los campos del §3 (A, B y C no usan
    las secciones opcionales de la segunda entrega: son la línea base)."""
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
    ("num_carros no positivo", {"num_carros": 0}, None, r"entero positivo"),
    ("num_cosechadoras no positivo", {"num_cosechadoras": 0}, None, r"entero positivo"),
    ("grano_por_celda no positivo", {"grano_por_celda": 0}, None, r"entero positivo"),
    ("tasa_transferencia no positiva", {"tasa_transferencia": 0}, None, r"entero positivo"),
    ("tasa_descarga negativa", {"tasa_descarga": -1}, None, r"entero positivo"),
    ("capacidad_cosechadora cero", {"capacidad_cosechadora": 0}, None, r"entero positivo"),
    ("capacidad_carro cero", {"capacidad_carro": 0}, None, r"entero positivo"),
    ("max_ticks cero", {"max_ticks": 0}, None, r"entero positivo"),
    ("obstáculos fuera del mapa", {"obstaculos": {"celdas": [[99, 99]], "regiones": []}}, None, r"fuera del mapa"),
    ("falta campo requerido", {}, "seed", r"falta seed"),
    ("campo desconocido", {"extra_parametro": 123}, None, r"desconocido"),
    # segunda entrega (§2): una prueba por validación de las secciones nuevas
    ("alto insuficiente para las franjas", {"alto": 3, "num_cosechadoras": 3, "ancho": 8}, None, r"alto insuficiente"),
    ("asignacion desconocida", {"politica": {"asignacion": "ruleta"}}, None, r"politica.asignacion"),
    ("umbral cero", {"politica": {"umbral_aviso": 0}}, None, r"politica.umbral_aviso"),
    ("umbral mayor a 1", {"politica": {"umbral_aviso": 1.5}}, None, r"politica.umbral_aviso"),
    ("umbral booleano", {"politica": {"umbral_aviso": True}}, None, r"politica.umbral_aviso"),
    ("atender_desde_bodega no booleano", {"politica": {"atender_desde_bodega": 1}}, None, r"politica.atender_desde_bodega"),
    ("espera_propuestas menor a 2", {"politica": {"espera_propuestas": 1}}, None, r"politica.espera_propuestas"),
    ("reintento_subasta cero", {"politica": {"reintento_subasta": 0}}, None, r"politica.reintento_subasta"),
    ("clave de politica desconocida", {"politica": {"prioridad": 1}}, None, r"politica.prioridad desconocido"),
    ("rendimiento minimo mayor que maximo", {"incertidumbre": {"rendimiento": {"minimo": 3, "maximo": 2}}}, None, r"incertidumbre.rendimiento"),
    ("rendimiento cero", {"incertidumbre": {"rendimiento": {"minimo": 0, "maximo": 2}}}, None, r"incertidumbre.rendimiento"),
    ("duracion extra negativa", {"incertidumbre": {"duracion_extra_maxima": -1}}, None, r"duracion_extra_maxima"),
    ("probabilidad de retraso mayor a 1", {"incertidumbre": {"retraso_mensajes": {"probabilidad": 1.2}}}, None, r"retraso_mensajes.probabilidad"),
    ("maximo de retraso negativo", {"incertidumbre": {"retraso_mensajes": {"maximo": -1}}}, None, r"retraso_mensajes.maximo"),
    ("tanque cero", {"combustible": {"tanque_carro": 0}}, None, r"combustible.tanque_carro"),
    ("consumo negativo", {"combustible": {"consumo_por_tick_encendido": -0.5}}, None, r"combustible.consumo_por_tick_encendido"),
    ("reserva igual a 1", {"combustible": {"reserva": 1}}, None, r"combustible.reserva"),
    ("tasa de recarga negativa", {"combustible": {"tasa_recarga": -1}}, None, r"combustible.tasa_recarga"),
    ("peso negativo", {"costo": {"pesos": {"ocio": -1}}}, None, r"costo.pesos.ocio"),
    ("termino de costo desconocido", {"costo": {"pesos": {"belleza": 1}}}, None, r"costo.pesos.belleza desconocido"),
    ("seccion que no es objeto", {"combustible": 5}, None, r"combustible debe ser un objeto"),
    ("capacidad menor que el rendimiento maximo", {"capacidad_cosechadora": 2, "incertidumbre": {"rendimiento": {"minimo": 1, "maximo": 3}}}, None, r"rendimiento máximo"),
]


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


def _cargar(tmp_path, **cambios):
    from harvest_sim.config import cargar_config
    datos = {**CONFIG_BASE, **cambios}
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return cargar_config(ruta)


def test_secciones_ausentes_usan_los_valores_por_defecto(tmp_path):
    """Sin las secciones nuevas, la configuración es la de la línea base (spec §2)."""
    from harvest_sim.config import COMBUSTIBLE_POR_DEFECTO, POLITICA_POR_DEFECTO
    from harvest_sim.datos.metricas import PESOS_COSTO

    config = _cargar(tmp_path)
    assert config.politica == POLITICA_POR_DEFECTO
    assert config.incertidumbre == {"rendimiento": {"minimo": 1, "maximo": 1}, "duracion_extra_maxima": 0,
                                    "retraso_mensajes": {"probabilidad": 0.0, "maximo": 0}}
    assert config.combustible == COMBUSTIBLE_POR_DEFECTO
    assert config.costo == {"pesos": PESOS_COSTO}


def test_secciones_parciales_se_completan(tmp_path):
    config = _cargar(tmp_path, politica={"asignacion": "subasta", "umbral_aviso": 0.7},
                     incertidumbre={"retraso_mensajes": {"probabilidad": 0.2}})
    assert config.politica["asignacion"] == "subasta" and config.politica["espera_propuestas"] == 2
    assert config.incertidumbre["retraso_mensajes"] == {"probabilidad": 0.2, "maximo": 0}
    assert config.incertidumbre["rendimiento"] == {"minimo": 1, "maximo": 1}


def test_el_rendimiento_por_defecto_es_grano_por_celda(tmp_path):
    config = _cargar(tmp_path, grano_por_celda=2)
    assert config.incertidumbre["rendimiento"] == {"minimo": 2, "maximo": 2}


def test_rendimiento_variable_no_exige_multiplo(tmp_path):
    config = _cargar(tmp_path, capacidad_cosechadora=7,
                     incertidumbre={"rendimiento": {"minimo": 1, "maximo": 2}})
    assert config.capacidad_cosechadora == 7


def test_varios_agentes_y_obstaculos_ya_se_aceptan(tmp_path):
    config = _cargar(tmp_path, num_carros=2, num_cosechadoras=2,
                     obstaculos={"celdas": [[2, 2]], "regiones": [{"inicio": [4, 3], "tamano": [2, 1]}]})
    assert (config.num_carros, config.num_cosechadoras) == (2, 2)


def test_los_defectos_no_se_comparten_entre_configuraciones(tmp_path):
    a = _cargar(tmp_path)
    a.politica["asignacion"] = "subasta"
    assert _cargar(tmp_path).politica["asignacion"] == "directa"


@pytest.mark.parametrize("nombre", ["escenario_d", "escenario_e", "escenario_f"])
def test_escenarios_de_la_segunda_entrega_cargan(nombre):
    from harvest_sim.config import cargar_config
    from harvest_sim.mundo import Mundo

    config = cargar_config(CONFIG_DIR / f"{nombre}.json")
    assert config.nombre == nombre
    mundo = Mundo(config)
    assert len(mundo.franjas()) == config.num_cosechadoras
