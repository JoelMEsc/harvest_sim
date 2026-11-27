"""Formato del trace (2.1, 2.2 y 2.3) y vocabulario compartido (estados, mensajes y clases de la ontología).  [Joel]

Es el único lugar donde se escriben estos nombres: las métricas, las gráficas, el validador y el resto
del equipo los importan desde aquí (`from harvest_sim.datos.formato import LLENA_ESPERANDO, ...`).
"""

from __future__ import annotations

SCHEMA_VERSION = "2.2"         # la que se escribe sin mapa (escenarios A-F)
SCHEMA_VERSION_MAPA = "2.3"    # la que se escribe cuando el mundo trae mapa (forma real, caminos, relieve)
SCHEMA_VERSION_HILERAS = "2.4"  # con politica.movimiento = "hileras": cabecera, pasadas y trayectorias de vuelta
VERSIONES_ACEPTADAS = ("2.1", "2.2", "2.3", "2.4")  # cada versión solo agrega campos a la anterior

# Campos opcionales de `mundo` que agrega el 2.3 (docs/especificacion_terreno.md §6). Si el mundo trae
# alguno, el trace es 2.3 y el campo cosechable sigue la regla del mapa (datos/campo.py).
CAMPOS_MUNDO_23 = ("tamano_celda_m", "caminos", "fuera_de_campo", "lotes", "altura_m", "geo")
# 2.4 (plan de hileras y rutas): celdas de cabecera y pasadas [x0, y, x1] (tramos de fila, hileras a lo largo de x)
CAMPOS_MUNDO_24 = ("cabecera", "pasadas")

# Claves del primer nivel y de cada tick, en este orden.
CLAVES_TRACE = ["schema_version", "meta", "config", "mundo", "agentes", "ticks", "metricas"]
CLAVES_TICK = ["tick", "cambios", "checksum"]

# Campos del registro de un agente que el log sigue; cualquier otro campo se ignora.
# `combustible` (2.2) es opcional: solo aparece si la simulación lo modela.
CAMPOS_AGENTE = ("pose", "estado", "carga", "combustible")
CAMPOS_AGENTE_OBLIGATORIOS = ("pose", "estado", "carga")  # los que debe traer el tick 0
ORIENTACIONES = ("N", "E", "S", "O")

# Categoría de cada tipo de evento: define el orden dentro del tick (estable dentro de la categoría).
CATEGORIA = {
    "MENSAJE_ENTREGADO": 0,
    "AGENTE": 1,
    "CELDA_COSECHADA": 2,
    "DEPOSITO": 2,
    "BLOQUEO": 2,
    "RECARGA": 2,
    "RESTRICCION": 2,
    "DECISION_DESPACHO": 2,
    "TRAYECTORIA": 2,
    "MENSAJE_ENVIADO": 3,
}

# Campos obligatorios (y su tipo) de cada evento. `float` significa número (int o float, sin bool).
CAMPOS_EVENTO = {
    "AGENTE": {"id": str, "set": dict},
    "CELDA_COSECHADA": {"celda": list, "agente": str},
    "DEPOSITO": {"agente": str, "cantidad": int, "entregado_total": int},
    "BLOQUEO": {"agente": str},
    "RECARGA": {"agente": str, "cantidad": float, "nivel": float},
    "RESTRICCION": {"agente": str, "regla": str, "detalle": str},
    # M1 (docs/especificacion_mejoras.md): una decisión de la tabla aprendida; solo con politica.aviso aprendido.
    "DECISION_DESPACHO": {"agente": str, "estado": dict, "accion": str, "origen": str},
    # 2.4: la curva (Dubins) de una vuelta de cabecera; puntos [x, y, rumbo] en metros del marco de la cuadrícula
    # (celda (c, f) centrada en (c·s, f·s); rumbo en radianes, 0 = +x, hacia +y positivo) y los ticks que dura.
    "TRAYECTORIA": {"agente": str, "tramo": str, "puntos": list, "ticks": int},
    "MENSAJE_ENVIADO": {"id": int, "tipo_mensaje": str, "performativa": str, "de": str, "a": str,
                        "payload": dict, "entrega_en": int},
    "MENSAJE_ENTREGADO": {"id": int, "a": str},
}
# Campos opcionales por evento (se validan si vienen). `CELDA_COSECHADA.cantidad` (2.2) es el grano obtenido en
# esa celda; si falta, vale el rendimiento de `mundo.rendimiento` o `grano_por_celda`.
CAMPOS_EVENTO_OPCIONALES = {
    "CELDA_COSECHADA": {"cantidad": int},
    # Valores de la tabla en ese estado; falta si la tabla no lo conoce (decide el umbral de respaldo).
    "DECISION_DESPACHO": {"q": dict},
}
EVENTOS_DESDE = {"RECARGA": "2.2", "RESTRICCION": "2.2", "DECISION_DESPACHO": "2.2", "TRAYECTORIA": "2.4"}
TRAMOS_TRAYECTORIA = ("vuelta",)
# DECISION_DESPACHO: claves de `estado`, acciones y de dónde salió la decisión.
CAMPOS_ESTADO_DESPACHO = ("tramo", "carros_libres", "distancia", "otra_pidio")
ACCIONES_DESPACHO = ("seguir", "pedir")
ORIGENES_DESPACHO = ("tabla", "umbral", "forzada", "exploracion")

# --- Tipos de agente -----------------------------------------------------------------------------
COSECHADORA = "cosechadora"
CARRO = "carro"

# --- Estados (§5 de la especificación) -----------------------------------------------------------
EN_BASE = "EN_BASE"
YENDO_A_CAMPO = "YENDO_A_CAMPO"
COSECHANDO = "COSECHANDO"
LLENA_ESPERANDO = "LLENA_ESPERANDO"   # tiempo ocioso de la cosechadora
TRANSFIRIENDO = "TRANSFIRIENDO"
REGRESANDO_A_BASE = "REGRESANDO_A_BASE"
FIN = "FIN"
YENDO_A_COSECHADORA = "YENDO_A_COSECHADORA"
ESPERANDO_TRANSFERENCIA = "ESPERANDO_TRANSFERENCIA"
YENDO_A_BODEGA = "YENDO_A_BODEGA"
DESCARGANDO = "DESCARGANDO"

ESTADOS_COSECHADORA = (EN_BASE, YENDO_A_CAMPO, COSECHANDO, LLENA_ESPERANDO, TRANSFIRIENDO, REGRESANDO_A_BASE, FIN)
RECIBIENDO_EN_MARCHA = "RECIBIENDO_EN_MARCHA"  # H6: va al lado de la cosechadora y recibe sin detenerse
ESTADOS_CARRO = (EN_BASE, YENDO_A_COSECHADORA, ESPERANDO_TRANSFERENCIA, YENDO_A_BODEGA, DESCARGANDO,
                 REGRESANDO_A_BASE, RECIBIENDO_EN_MARCHA)
ESTADOS_CONOCIDOS = frozenset(ESTADOS_COSECHADORA) | frozenset(ESTADOS_CARRO)

# --- Mensajes y su acto comunicativo (performativa, como en KQML / FIPA-ACL) ---------------------
LLENA = "LLENA"
TRANSFERENCIA_TERMINADA = "TRANSFERENCIA_TERMINADA"
# Subasta Contract Net (especificación de la segunda entrega §7): la cosechadora administra, los carros ofertan.
SOLICITUD_SERVICIO = "SOLICITUD_SERVICIO"
PROPUESTA = "PROPUESTA"
RECHAZO = "RECHAZO"
ACEPTACION = "ACEPTACION"
RECHAZO_PROPUESTA = "RECHAZO_PROPUESTA"

PERFORMATIVAS = {
    LLENA: "request",                     # la cosechadora PIDE que el carro venga (modo directa)
    TRANSFERENCIA_TERMINADA: "inform",    # la cosechadora AVISA que terminó la transferencia
    SOLICITUD_SERVICIO: "cfp",            # llamada a propuestas
    PROPUESTA: "propose",                 # el carro ofrece su costo
    RECHAZO: "refuse",                    # el carro no puede atender
    ACEPTACION: "accept-proposal",        # la cosechadora adjudica el servicio
    RECHAZO_PROPUESTA: "reject-proposal",  # la cosechadora descarta las demás ofertas
}
PERFORMATIVAS_VALIDAS = tuple(dict.fromkeys(PERFORMATIVAS.values()))
TIPOS_MENSAJE = tuple(PERFORMATIVAS)

# Claves obligatorias del payload de cada mensaje (puede traer otras).
PAYLOAD_POR_TIPO = {
    LLENA: ("x", "y", "carga"),
    TRANSFERENCIA_TERMINADA: ("cantidad",),
    SOLICITUD_SERVICIO: ("servicio", "x", "y", "carga", "capacidad"),
    PROPUESTA: ("servicio", "costo"),
    RECHAZO: ("servicio", "motivo"),
    ACEPTACION: ("servicio",),
    RECHAZO_PROPUESTA: ("servicio",),
}
MOTIVOS_RECHAZO = ("sin_capacidad", "combustible", "sin_ruta")

# --- Restricciones de seguridad registradas (evento RESTRICCION, IEEE 7007) -----------------------
R3_CELDA_OCUPADA = "R3_celda_ocupada"
R4_INTERCAMBIO = "R4_intercambio"
R9_BODEGA = "R9_bodega"
R10_OBSTACULO = "R10_obstaculo"
COMBUSTIBLE_RESERVA = "combustible_reserva"
R12_FUERA_DE_CAMPO = "R12_fuera_de_campo"    # 2.3: nadie sale del predio
R13_CULTIVO_EN_PIE = "R13_cultivo_en_pie"    # 2.3: los carros no pisan el cultivo sin cosechar
R14_HILERAS = "R14_hileras"                  # hileras: a una pasada se entra de frente, nunca de lado
REGLAS_RESTRICCION = (R3_CELDA_OCUPADA, R4_INTERCAMBIO, R9_BODEGA, R10_OBSTACULO, COMBUSTIBLE_RESERVA,
                      R12_FUERA_DE_CAMPO, R13_CULTIVO_EN_PIE, R14_HILERAS)

# --- Clases de la ontología del curso (docs/ontologia.md) ----------------------------------------
CLASE_REGISTRO = "AccountabilityRecord"         # meta.clase: el trace es un registro verificable
CLASE_AGENTE = "AutonomousAgriculturalRobot"    # agentes[].clase
CLASE_CELDAS = "SemanticMapCell"                # mundo.clase_celdas: las celdas del grid tienen significado
