
"""Carga y validación de la configuración de un escenario.

Especificación: sección 3.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path

from .datos.campo import expandir_obstaculos


@dataclass(frozen=True)
class Config:
    nombre: str
    seed: int
    ancho: int
    alto: int
    num_carros: int
    num_cosechadoras: int
    grano_por_celda: int
    capacidad_cosechadora: int
    capacidad_carro: int
    tasa_transferencia: int
    tasa_descarga: int
    max_ticks: int
    obstaculos: dict = field(
        default_factory=lambda: {"celdas": [], "regiones": []}
    )


def cargar_config(ruta: str | Path) -> Config:
    """Lee un escenario JSON, valida sus parámetros y devuelve un Config."""

    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"config: JSON inválido: {error}") from error

    if not isinstance(datos, dict):
        raise ValueError("config: se esperaba un objeto JSON")

    # verificar que estén todos los campos esperados
    campos_esperados = {campo.name for campo in fields(Config)}
    faltantes = campos_esperados - datos.keys()
    sobrantes = datos.keys() - campos_esperados

    if faltantes:
        raise ValueError(f"config: falta {sorted(faltantes)[0]}")

    if sobrantes:
        raise ValueError(f"config: campo desconocido {sorted(sobrantes)[0]}")

    if not isinstance(datos["nombre"], str) or not datos["nombre"].strip():
        raise ValueError("config: nombre debe ser un texto no vacío")

    # seed puede ser cero, a diferencia de los demás parámetros numéricos
    if type(datos["seed"]) is not int or datos["seed"] < 0:
        raise ValueError("config: seed debe ser un entero no negativo")

    campos_positivos = (
        "ancho",
        "alto",
        "num_carros",
        "num_cosechadoras",
        "grano_por_celda",
        "capacidad_cosechadora",
        "capacidad_carro",
        "tasa_transferencia",
        "tasa_descarga",
        "max_ticks",
    )

    for campo in campos_positivos:
        valor = datos[campo]
        if type(valor) is not int or valor <= 0:
            raise ValueError(f"config: {campo} debe ser un entero positivo")

    # por ahora solo se permite una cosechadora y un carro
    if datos["num_carros"] != 1:
        raise ValueError("config: num_carros distinto de 1 aún no soportado")

    if datos["num_cosechadoras"] != 1:
        raise ValueError("config: num_cosechadoras distinto de 1 aún no soportado")

    if datos["ancho"] < 1 + datos["num_carros"] + datos["num_cosechadoras"]:
        raise ValueError("config: ancho insuficiente para la bodega y las bases")

    if datos["alto"] < 2:
        raise ValueError("config: alto debe ser al menos 2")

    if datos["capacidad_carro"] < datos["capacidad_cosechadora"]:
        raise ValueError(
            "config: capacidad_carro debe ser mayor o igual a capacidad_cosechadora"
        )

    if datos["capacidad_cosechadora"] % datos["grano_por_celda"] != 0:
        raise ValueError(
            "config: capacidad_cosechadora debe ser múltiplo de grano_por_celda"
        )

    # validar los obstáculos usando la función compartida del proyecto
    celdas = expandir_obstaculos(
        datos["obstaculos"],
        datos["ancho"],
        datos["alto"],
    )

    if celdas:
        raise ValueError("config: obstáculos aún no soportados en esta entrega")

    return Config(**datos)
