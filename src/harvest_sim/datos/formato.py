"""Formato del trace 2.1 y vocabulario compartido (estados, mensajes y clases de la ontología).  [Joel]

Es el único lugar donde se escriben estos nombres: las métricas, las gráficas, el validador y el resto
del equipo los importan desde aquí (`from harvest_sim.datos.formato import LLENA_ESPERANDO, ...`).
"""

from __future__ import annotations

SCHEMA_VERSION = "2.1"

# Claves del primer nivel y de cada tick, en este orden.
CLAVES_TRACE = ["schema_version", "meta", "config", "mundo", "agentes", "ticks", "metricas"]
CLAVES_TICK = ["tick", "cambios", "checksum"]

# Campos del registro de un agente que el log sigue; cualquier otro campo se ignora.
CAMPOS_AGENTE = ("pose", "estado", "carga")
ORIENTACIONES = ("N", "E", "S", "O")

# Categoría de cada tipo de evento: define el orden dentro del tick (estable dentro de la categoría).
CATEGORIA = {
    "MENSAJE_ENTREGADO": 0,
    "AGENTE": 1,
    "CELDA_COSECHADA": 2,
    "DEPOSITO": 2,
    "BLOQUEO": 2,
    "MENSAJE_ENVIADO": 3,
}

# Campos obligatorios (y su tipo) de cada evento.
CAMPOS_EVENTO = {
    "AGENTE": {"id": str, "set": dict},
    "CELDA_COSECHADA": {"celda": list, "agente": str},
    "DEPOSITO": {"agente": str, "cantidad": int, "entregado_total": int},
    "BLOQUEO": {"agente": str},
    "MENSAJE_ENVIADO": {"id": int, "tipo_mensaje": str, "performativa": str, "de": str, "a": str,
                        "payload": dict, "entrega_en": int},
    "MENSAJE_ENTREGADO": {"id": int, "a": str},
}

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
ESTADOS_CARRO = (EN_BASE, YENDO_A_COSECHADORA, ESPERANDO_TRANSFERENCIA, YENDO_A_BODEGA, DESCARGANDO,
                 REGRESANDO_A_BASE)
ESTADOS_CONOCIDOS = frozenset(ESTADOS_COSECHADORA) | frozenset(ESTADOS_CARRO)

# --- Mensajes y su acto comunicativo (performativa, como en KQML / FIPA-ACL) ---------------------
LLENA = "LLENA"
TRANSFERENCIA_TERMINADA = "TRANSFERENCIA_TERMINADA"
PERFORMATIVAS = {
    LLENA: "request",                    # la cosechadora PIDE que el carro venga
    TRANSFERENCIA_TERMINADA: "inform",   # la cosechadora AVISA que terminó la transferencia
}
PERFORMATIVAS_VALIDAS = ("request", "inform")

# --- Clases de la ontología del curso (docs/ontologia.md) ----------------------------------------
CLASE_REGISTRO = "AccountabilityRecord"         # meta.clase: el trace es un registro verificable
CLASE_AGENTE = "AutonomousAgriculturalRobot"    # agentes[].clase
CLASE_CELDAS = "SemanticMapCell"                # mundo.clase_celdas: las celdas del grid tienen significado
