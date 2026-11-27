"""Carga y validación de la configuración de un escenario.

Especificación: sección 3 (primera entrega) y §2 de la segunda entrega. Las secciones nuevas
(`politica`, `incertidumbre`, `combustible`, `costo`) son opcionales: si faltan, se usan los valores por
defecto, que reproducen la primera entrega.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field, fields
from pathlib import Path

from .datos.campo import celdas_de_campo, expandir_obstaculos
from .datos.metricas import PESOS_COSTO

# Valores por defecto de la especificación de la segunda entrega §2 (= línea base de la primera).
POLITICA_POR_DEFECTO = {
    "asignacion": "directa",
    "umbral_aviso": 1.0,
    "atender_desde_bodega": False,
    "encadenar_servicios": False,
    "espera_propuestas": 2,
    "reintento_subasta": 3,
    # R13 (docs/especificacion_terreno.md §7): los carros no pisan el cultivo en pie. Solo tiene efecto
    # con mapa; apagado por defecto para que A-F no cambien.
    "respetar_cultivo": False,
    # M1 (docs/especificacion_mejoras.md): cuándo pide carro la cosechadora en subasta. "umbral" = la regla
    # fija de umbral_aviso; "qlearning" o "sarsa" = la tabla aprendida (qtabla, relativa a config/; None =
    # config/aprendizaje/qtabla_<algoritmo>_<escenario>.json). Desactivado por defecto.
    "aviso": "umbral",
    "qtabla": None,
    # Plan de hileras y rutas: "celdas" = el movimiento de siempre (por celdas, BFS); "hileras" = cabeceras,
    # pasadas paralelas a las hileras, vueltas con radio de giro y A* con rumbo. Desactivado por defecto.
    "movimiento": "celdas",
    # H6, descarga en marcha (como Machine Sync o Raven Cart Automation): el carro se pone al lado de la
    # cosechadora, sobre el rastrojo, y recibe el grano mientras ella sigue cosechando. Requiere hileras y
    # subasta (con asignación directa no tiene efecto). Desactivada por defecto.
    "descarga_en_marcha": False,
}
INCERTIDUMBRE_POR_DEFECTO = {
    # None = {minimo: grano_por_celda, maximo: grano_por_celda}: depende de otro campo
    "rendimiento": None,
    "duracion_extra_maxima": 0,
    "retraso_mensajes": {"probabilidad": 0.0, "maximo": 0},
}
COMBUSTIBLE_POR_DEFECTO = {
    "tanque_cosechadora": 100000,
    "tanque_carro": 100000,
    "consumo_por_celda_cosechadora": 2.0,
    "consumo_por_celda_carro": 1.0,
    "consumo_por_tick_encendido": 0.5,
    "reserva": 0.15,
    "tasa_recarga": 0,
    # Consumo extra al subir (docs/especificacion_terreno.md §8): por celda, × (1 + f · pendiente_% / 100).
    # 0 = sin efecto (A-F no cambian). Solo aplica si el mapa trae altura_m.
    "factor_pendiente": 0.0,
}
COSTO_POR_DEFECTO = {"pesos": dict(PESOS_COSTO)}
# Plan de hileras y rutas: lo que limita el movimiento con politica.movimiento = "hileras". Supuestos de una
# cosechadora con cabezal maicero de 16 hileras (12 m): radio de giro mínimo ~7.5 m, ~6 km/h cosechando y ~5
# km/h en la vuelta de cabecera. Con "celdas" no se usan (ni van al trace).
MAQUINAS_POR_DEFECTO = {"radio_giro_m": 7.5, "velocidad_cosecha_kmh": 6.0, "velocidad_vuelta_kmh": 5.0,
                        # tractor con carro tolva: gira más cerrado y anda más rápido en el campo que la cosechadora
                        "radio_giro_carro_m": 6.0, "velocidad_carro_kmh": 10.0}

ASIGNACIONES = ("directa", "subasta")
AVISOS = ("umbral", "qlearning", "sarsa")
MOVIMIENTOS = ("celdas", "hileras")
SECCIONES_OPCIONALES = ("politica", "incertidumbre", "combustible", "costo", "maquinas")


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
    politica: dict = field(default_factory=lambda: copy.deepcopy(POLITICA_POR_DEFECTO))
    incertidumbre: dict = field(default_factory=dict)  # se completa en __post_init__ (depende de grano)
    combustible: dict = field(default_factory=lambda: copy.deepcopy(COMBUSTIBLE_POR_DEFECTO))
    costo: dict = field(default_factory=lambda: copy.deepcopy(COSTO_POR_DEFECTO))
    maquinas: dict = field(default_factory=lambda: copy.deepcopy(MAQUINAS_POR_DEFECTO))
    # Mapa real (docs/especificacion_terreno.md §5): el contenido de config/mapas/*.json, más "archivo" y
    # "sha256". None = el mundo rectangular de siempre.
    mapa: dict | None = None

    def __post_init__(self) -> None:
        # Un Config creado en código (pruebas) también trae todas las claves de cada sección.
        completas = {
            "politica": _con_defectos("politica", self.politica, POLITICA_POR_DEFECTO),
            "incertidumbre": _con_defectos(
                "incertidumbre", self.incertidumbre, _incertidumbre_por_defecto(self.grano_por_celda)
            ),
            "combustible": _con_defectos("combustible", self.combustible, COMBUSTIBLE_POR_DEFECTO),
            "costo": _con_defectos("costo", self.costo, COSTO_POR_DEFECTO),
            "maquinas": _con_defectos("maquinas", self.maquinas, MAQUINAS_POR_DEFECTO),
        }
        for nombre, valor in completas.items():
            object.__setattr__(self, nombre, valor)


# Campos que todo JSON de escenario debe traer (los de la primera entrega; obstaculos tiene defecto).
OBLIGATORIOS = tuple(
    f.name for f in fields(Config) if f.name not in SECCIONES_OPCIONALES + ("obstaculos", "mapa")
)

# Carpeta config/ del repositorio: ahí se buscan los mapas si no están junto al JSON del escenario
# (los experimentos y el servidor escriben la configuración en un directorio temporal).
CARPETA_CONFIG = Path(__file__).resolve().parents[2] / "config"
CLAVES_MAPA = ("tamano_celda_m", "ancho", "alto", "bodega", "bases", "obstaculos", "caminos", "fuera_de_campo",
               "lotes", "geo")


def cargar_mapa(nombre: str, carpeta: str | Path | None = None) -> dict:
    """Lee config/mapas/*.json (relativo a `carpeta` o a config/ del repo) y le agrega archivo y sha256."""
    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError("config: mapa debe ser la ruta de un archivo de config/mapas/")
    candidatos = [Path(nombre)] if Path(nombre).is_absolute() else \
        [Path(carpeta) / nombre] * (carpeta is not None) + [CARPETA_CONFIG / nombre]
    ruta = next((c for c in candidatos if c.is_file()), None)
    if ruta is None:
        raise ValueError(f"config: no existe el mapa {nombre}")
    texto = ruta.read_bytes()
    try:
        mapa = json.loads(texto.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"config: el mapa {nombre} no es JSON válido: {error}") from error
    faltan = [c for c in CLAVES_MAPA if c not in mapa]
    if faltan:
        raise ValueError(f"config: al mapa {nombre} le falta {faltan[0]}")
    mapa["archivo"] = nombre
    mapa["sha256"] = hashlib.sha256(texto).hexdigest()
    return mapa


def _incertidumbre_por_defecto(grano_por_celda: int) -> dict:
    defectos = copy.deepcopy(INCERTIDUMBRE_POR_DEFECTO)
    defectos["rendimiento"] = {"minimo": grano_por_celda, "maximo": grano_por_celda}
    return defectos


def _con_defectos(ruta: str, valor, defectos: dict) -> dict:
    """Completa las claves que falten con los defectos (también en los dicts anidados) y rechaza las
    desconocidas. Devuelve un dict nuevo: nunca comparte ni modifica los defectos."""
    if valor is None:
        valor = {}
    if not isinstance(valor, dict):
        raise ValueError(f"config: {ruta} debe ser un objeto")
    desconocidas = sorted(set(valor) - set(defectos))
    if desconocidas:
        raise ValueError(f"config: {ruta}.{desconocidas[0]} desconocido")
    resultado = {}
    for clave, defecto in defectos.items():
        if isinstance(defecto, dict):
            resultado[clave] = _con_defectos(f"{ruta}.{clave}", valor.get(clave), defecto)
        else:
            resultado[clave] = copy.deepcopy(valor.get(clave, defecto))
    return resultado


def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _es_entero(v) -> bool:
    return type(v) is int


def _validar_secciones(datos: dict) -> None:
    pol = datos["politica"]
    if pol["asignacion"] not in ASIGNACIONES:
        raise ValueError(f"config: politica.asignacion debe ser una de {list(ASIGNACIONES)}")
    if not _es_numero(pol["umbral_aviso"]) or not 0 < pol["umbral_aviso"] <= 1:
        raise ValueError("config: politica.umbral_aviso debe estar en (0, 1]")
    for clave in ("atender_desde_bodega", "encadenar_servicios", "respetar_cultivo", "descarga_en_marcha"):
        if not isinstance(pol[clave], bool):
            raise ValueError(f"config: politica.{clave} debe ser true o false")
    for clave, valor in datos["maquinas"].items():
        if not _es_numero(valor) or valor <= 0:
            raise ValueError(f"config: maquinas.{clave} debe ser un número > 0")
    if pol["movimiento"] not in MOVIMIENTOS:
        raise ValueError(f"config: politica.movimiento debe ser uno de {list(MOVIMIENTOS)}")
    if pol["aviso"] not in AVISOS:
        raise ValueError(f"config: politica.aviso debe ser uno de {list(AVISOS)}")
    if pol["aviso"] != "umbral" and pol["asignacion"] != "subasta":
        raise ValueError("config: politica.aviso aprendido requiere politica.asignacion = subasta")
    if pol["qtabla"] is not None and (not isinstance(pol["qtabla"], str) or not pol["qtabla"]):
        raise ValueError("config: politica.qtabla debe ser una ruta (texto) o null")
    if not _es_entero(pol["espera_propuestas"]) or pol["espera_propuestas"] < 2:
        raise ValueError("config: politica.espera_propuestas debe ser un entero >= 2")
    if not _es_entero(pol["reintento_subasta"]) or pol["reintento_subasta"] < 1:
        raise ValueError("config: politica.reintento_subasta debe ser un entero >= 1")

    inc = datos["incertidumbre"]
    rend = inc["rendimiento"]
    if not (_es_entero(rend["minimo"]) and _es_entero(rend["maximo"]) and 1 <= rend["minimo"] <= rend["maximo"]):
        raise ValueError("config: incertidumbre.rendimiento debe cumplir 1 <= minimo <= maximo (enteros)")
    if not _es_entero(inc["duracion_extra_maxima"]) or inc["duracion_extra_maxima"] < 0:
        raise ValueError("config: incertidumbre.duracion_extra_maxima debe ser un entero >= 0")
    retraso = inc["retraso_mensajes"]
    if not _es_numero(retraso["probabilidad"]) or not 0 <= retraso["probabilidad"] <= 1:
        raise ValueError("config: incertidumbre.retraso_mensajes.probabilidad debe estar en [0, 1]")
    if not _es_entero(retraso["maximo"]) or retraso["maximo"] < 0:
        raise ValueError("config: incertidumbre.retraso_mensajes.maximo debe ser un entero >= 0")

    comb = datos["combustible"]
    for clave in ("tanque_cosechadora", "tanque_carro", "consumo_por_celda_cosechadora",
                  "consumo_por_celda_carro", "consumo_por_tick_encendido"):
        if not _es_numero(comb[clave]) or comb[clave] <= 0:
            raise ValueError(f"config: combustible.{clave} debe ser un número > 0")
    if not _es_numero(comb["reserva"]) or not 0 <= comb["reserva"] < 1:
        raise ValueError("config: combustible.reserva debe estar en [0, 1)")
    if not _es_numero(comb["factor_pendiente"]) or comb["factor_pendiente"] < 0:
        raise ValueError("config: combustible.factor_pendiente debe ser un número >= 0")
    if not _es_numero(comb["tasa_recarga"]) or comb["tasa_recarga"] < 0:
        raise ValueError("config: combustible.tasa_recarga debe ser un número >= 0")

    for clave, peso in datos["costo"]["pesos"].items():
        if not _es_numero(peso) or peso < 0:
            raise ValueError(f"config: costo.pesos.{clave} debe ser un número >= 0")


def cargar_config(ruta: str | Path) -> Config:
    """Lee un escenario JSON, valida sus parámetros y devuelve un Config."""

    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"config: JSON inválido: {error}") from error

    if not isinstance(datos, dict):
        raise ValueError("config: se esperaba un objeto JSON")

    # con mapa, el tamaño y los obstáculos vienen del mapa
    if "mapa" in datos and datos["mapa"] is not None:
        mapa = cargar_mapa(datos["mapa"], Path(ruta).parent)
        for clave in ("ancho", "alto"):
            if clave in datos and datos[clave] != mapa[clave]:
                raise ValueError(f"config: {clave} ({datos[clave]}) no coincide con el del mapa ({mapa[clave]})")
            datos[clave] = mapa[clave]
        obst = datos.get("obstaculos") or {}
        if obst.get("celdas") or obst.get("regiones"):
            raise ValueError("config: con mapa, los obstáculos vienen del mapa (quita la sección obstaculos)")
        datos["mapa"] = mapa

    # verificar que estén los campos obligatorios y ninguno desconocido
    conocidos = {campo.name for campo in fields(Config)}
    faltantes = set(OBLIGATORIOS) - datos.keys()
    sobrantes = datos.keys() - conocidos

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

    if datos.get("mapa") is not None:
        if len(datos["mapa"]["bases"]) < datos["num_carros"] + datos["num_cosechadoras"]:
            raise ValueError(f"config: el mapa tiene {len(datos['mapa']['bases'])} bases y hay "
                             f"{datos['num_carros'] + datos['num_cosechadoras']} agentes")
    else:
        if datos["ancho"] < 1 + datos["num_carros"] + datos["num_cosechadoras"]:
            raise ValueError("config: ancho insuficiente para la bodega y las bases")

        if datos["alto"] < 2:
            raise ValueError("config: alto debe ser al menos 2")

        # cada cosechadora recorre una franja de al menos una fila del campo (filas 1..alto-1)
        if datos["alto"] - 1 < datos["num_cosechadoras"]:
            raise ValueError("config: alto insuficiente: cada cosechadora necesita al menos una fila del campo")

    if datos["capacidad_carro"] < datos["capacidad_cosechadora"]:
        raise ValueError(
            "config: capacidad_carro debe ser mayor o igual a capacidad_cosechadora"
        )

    # completar las secciones opcionales con sus defectos y validarlas
    datos["politica"] = _con_defectos("politica", datos.get("politica"), POLITICA_POR_DEFECTO)
    datos["incertidumbre"] = _con_defectos(
        "incertidumbre", datos.get("incertidumbre"), _incertidumbre_por_defecto(datos["grano_por_celda"])
    )
    datos["combustible"] = _con_defectos("combustible", datos.get("combustible"), COMBUSTIBLE_POR_DEFECTO)
    datos["costo"] = _con_defectos("costo", datos.get("costo"), COSTO_POR_DEFECTO)
    datos["maquinas"] = _con_defectos("maquinas", datos.get("maquinas"), MAQUINAS_POR_DEFECTO)
    _validar_secciones(datos)
    if datos["politica"]["descarga_en_marcha"] and datos["politica"]["movimiento"] != "hileras":
        # solo actúa con asignacion = subasta (el carro con servicio contratado); con directa no tiene efecto
        raise ValueError("config: politica.descarga_en_marcha requiere movimiento = hileras")
    if datos["politica"]["movimiento"] == "hileras" and datos.get("mapa") is None:
        raise ValueError("config: politica.movimiento = hileras requiere un mapa (las hileras y los lotes vienen de él)")

    # Con rendimiento fijo, la tolva se llena exacto si su capacidad es múltiplo del grano de una celda.
    # Con rendimiento variable no se exige: la cosechadora se considera llena antes (spec §8).
    rendimiento = datos["incertidumbre"]["rendimiento"]
    if rendimiento["minimo"] == rendimiento["maximo"]:
        if datos["capacidad_cosechadora"] % rendimiento["minimo"] != 0:
            raise ValueError(
                "config: capacidad_cosechadora debe ser múltiplo de grano_por_celda"
                " (o del rendimiento fijo de cada celda)"
            )
    if datos["capacidad_cosechadora"] < rendimiento["maximo"]:
        raise ValueError("config: capacidad_cosechadora menor que el rendimiento máximo de una celda")

    # validar los obstáculos usando la función compartida del proyecto (mapa, fila 0, alcanzabilidad)
    datos.setdefault("obstaculos", {"celdas": [], "regiones": []})
    celdas = expandir_obstaculos(
        datos["obstaculos"],
        datos["ancho"],
        datos["alto"],
    )
    libres = celdas_de_campo({"ancho": datos["ancho"], "alto": datos["alto"], "obstaculos": celdas})
    if not libres:
        raise ValueError("config: el campo no tiene celdas libres")

    return Config(**datos)
