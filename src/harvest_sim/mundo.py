"""Estado físico del mundo: campo, agentes, grano, reservas, azar, combustible y eventos.

Especificación: secciones 2, 4.2 y 4.3 (primera entrega); §3, §4, §5, §8, §9 y §10 de la segunda.
"""

from __future__ import annotations

import logging
import random

from .config import Config
from .datos.campo import celdas_de_campo, expandir_obstaculos, grano_esperado
from .datos.formato import REGLAS_RESTRICCION
from . import rutas

Celda = tuple[int, int]

registrador = logging.getLogger("harvest_sim.mundo")

# Estados en que el motor está apagado: no se consume combustible por estar encendido y, en la base,
# se recarga (spec §9).
APAGADO = ("EN_BASE", "FIN")


def _texto(estado) -> str:
    return getattr(estado, "value", estado)


class Mundo:
    """Almacena el estado del entorno y centraliza las operaciones con grano, reservas y combustible."""

    bodega: Celda = (0, 0)

    def __init__(self, config: Config) -> None:
        self.config = config  # los agentes leen las tasas y la política de aquí
        self.ancho = config.ancho
        self.alto = config.alto
        self.grano_por_celda = config.grano_por_celda
        self.entregado = 0

        # asignar las bases según la cantidad de agentes
        self._bases: dict[str, Celda] = {}
        for indice in range(1, config.num_carros + 1):
            self._bases[f"carro_{indice}"] = (indice, 0)
        for indice in range(1, config.num_cosechadoras + 1):
            self._bases[f"cosechadora_{indice}"] = (config.num_carros + indice, 0)

        self._lista_obstaculos = expandir_obstaculos(config.obstaculos, self.ancho, self.alto)
        self.obstaculos: frozenset[Celda] = frozenset(tuple(c) for c in self._lista_obstaculos)

        self._agentes = {}
        self._cosechadas: dict[Celda, int] = {}  # celda -> grano obtenido
        self._eventos: list[dict] = []
        self._reservas: dict[tuple[Celda, int], str] = {}
        self._azar: dict[str, random.Random] = {}
        self._caminos: dict[str, list[Celda]] = {}

        descripcion = self._descripcion_sin_rendimiento()
        self._celdas_campo = celdas_de_campo(descripcion)
        self._rendimiento = self._sortear_rendimiento()
        self._franjas = self._calcular_franjas()
        self.grano_total = grano_esperado(self.descripcion())

    # ------------------------------------------------------------------ agentes

    def registrar(self, agente) -> None:
        """Registra el agente, lo coloca en su base y le llena el tanque."""
        identificador = agente.agent_id

        if identificador not in self._bases:
            raise ValueError(f"agente desconocido: {identificador}")
        if identificador in self._agentes:
            raise ValueError(f"agente ya registrado: {identificador}")

        agente.posicion = self.base_de(identificador)
        tanque = float(self.config.combustible[f"tanque_{self._tipo(identificador)}"])
        agente.tanque = tanque
        agente.combustible = tanque
        self._agentes[identificador] = agente

    def base_de(self, agent_id: str) -> Celda:
        """Devuelve la base asignada al agente."""
        return self._bases[agent_id]

    def posicion(self, agent_id: str) -> Celda:
        """Consulta la posición actual del agente (KeyError si no existe)."""
        return self._agentes[agent_id].posicion

    def estado_de(self, agent_id: str) -> str:
        """Consulta el estado del agente como texto."""
        return _texto(self._agentes[agent_id].estado)

    def ocupadas(self, excepto: str) -> set[Celda]:
        """Devuelve las posiciones ocupadas por otros agentes."""
        return {
            agente.posicion
            for identificador, agente in self._agentes.items()
            if identificador != excepto
        }

    def bloqueadas_fijas(self, agent_id: str) -> set[Celda]:
        """Obstáculos para todos (R10); además, la bodega para las cosechadoras (R9)."""
        fijas = set(self.obstaculos)
        if agent_id.startswith("cosechadora_"):
            fijas.add(self.bodega)
        return fijas

    @staticmethod
    def _tipo(agent_id: str) -> str:
        return "cosechadora" if agent_id.startswith("cosechadora_") else "carro"

    # ------------------------------------------------------------------ campo

    def _descripcion_sin_rendimiento(self) -> dict:
        return {
            "ancho": self.ancho,
            "alto": self.alto,
            "bodega": list(self.bodega),
            "bases": {identificador: list(celda) for identificador, celda in self._bases.items()},
            "grano_por_celda": self.grano_por_celda,
            "obstaculos": [list(celda) for celda in self._lista_obstaculos],
        }

    def _sortear_rendimiento(self) -> dict[Celda, int]:
        """Grano de cada celda libre del campo. Fijo: sin llamar al generador (no cambia la secuencia);
        variable: sorteado en orden (y, x), que es determinista (spec §8)."""
        rango = self.config.incertidumbre["rendimiento"]
        minimo, maximo = rango["minimo"], rango["maximo"]
        orden = sorted(self._celdas_campo, key=lambda c: (c[1], c[0]))
        if minimo == maximo:
            return {celda: minimo for celda in orden}
        azar = self.azar("rendimiento")
        return {celda: azar.randint(minimo, maximo) for celda in orden}

    def rendimiento(self, celda: Celda) -> int:
        """Grano que da la celda (0 fuera del campo)."""
        return self._rendimiento.get(tuple(celda), 0)

    def _calcular_franjas(self) -> list[list[int]]:
        """Divide las filas del campo (1..alto-1) en m franjas de filas contiguas con un número de celdas
        libres lo más parejo posible (spec §3). Cada corte va después de la fila cuyo acumulado queda
        más cerca de k·N/m; en empate, la franja de arriba se queda con la fila. Devuelve las filas de
        cada franja."""
        m = self.config.num_cosechadoras
        filas = list(range(1, self.alto))
        por_fila = [sum(1 for x in range(self.ancho) if (x, y) not in self.obstaculos) for y in filas]
        total = sum(por_fila)
        acumulado = []
        suma = 0
        for cantidad in por_fila:
            suma += cantidad
            acumulado.append(suma)

        cortes = []  # índice (en `filas`) de la última fila de cada franja, salvo la última
        anterior = -1
        for k in range(1, m):
            objetivo = k * total / m
            # deja al menos una fila para cada franja que falta
            candidatos = range(anterior + 1, len(filas) - (m - k))
            mejor = min(candidatos, key=lambda i: (abs(acumulado[i] - objetivo), -acumulado[i]))
            cortes.append(mejor)
            anterior = mejor

        franjas = []
        inicio = 0
        for fin in cortes + [len(filas) - 1]:
            franja = filas[inicio:fin + 1]
            if not any(por_fila[i] for i in range(inicio, fin + 1)):
                raise ValueError(f"la franja de las filas {franja} no tiene celdas libres")
            franjas.append(franja)
            inicio = fin + 1
        return franjas

    def franjas(self) -> list[list[int]]:
        """Filas de la franja de cada cosechadora (en orden: cosechadora_1, cosechadora_2, ...)."""
        return [list(f) for f in self._franjas]

    def camino(self, agent_id: str) -> list[Celda]:
        """Serpentina de la franja de esa cosechadora, sin obstáculos. Paridad global (fila impar:
        x creciente), así que con una cosechadora y sin obstáculos es la serpentina de v0.1."""
        if agent_id not in self._caminos:
            if not agent_id.startswith("cosechadora_"):
                raise ValueError(f"solo las cosechadoras tienen camino: {agent_id}")
            j = int(agent_id.rsplit("_", 1)[1])
            if not 1 <= j <= len(self._franjas):
                raise KeyError(agent_id)
            camino = []
            for y in self._franjas[j - 1]:
                columnas = range(self.ancho) if y % 2 else range(self.ancho - 1, -1, -1)
                camino.extend((x, y) for x in columnas if (x, y) not in self.obstaculos)
            self._caminos[agent_id] = camino
        return list(self._caminos[agent_id])

    def camino_serpentina(self) -> list[Celda]:
        """Camino de la primera cosechadora (se conserva para el código de la primera entrega)."""
        return self.camino("cosechadora_1")

    def vecinos(self, celda: Celda) -> list[Celda]:
        """Obtiene las celdas adyacentes mediante el módulo de rutas."""
        return rutas.vecinos(celda, self.ancho, self.alto)

    def ruta_bfs(
        self, origen: Celda, destino: Celda, bloqueadas: set[Celda]
    ) -> list[Celda] | None:
        """Ruta más corta (módulo de rutas); los obstáculos siempre cuentan como bloqueados."""
        return rutas.bfs(
            origen, destino, self.ancho, self.alto, set(bloqueadas) | self.obstaculos
        )

    # ---------------------------------------------------------------- reservas

    def reservar(self, agent_id: str, ruta: list[tuple[Celda, int]]) -> None:
        """Reemplaza las reservas de `agent_id` desde el primer tick de `ruta` (spec §5).
        Si otro agente ya reservó esa (celda, tick), se respeta la suya: gana quien reservó primero,
        que es quien actúa antes en el tick (cosechadoras, luego carros, por id)."""
        if not ruta:
            return
        desde = min(t for _, t in ruta)
        self._reservas = {
            clave: dueno for clave, dueno in self._reservas.items()
            if not (dueno == agent_id and clave[1] >= desde)
        }
        for celda, t in ruta:
            clave = (tuple(celda), t)
            dueno = self._reservas.get(clave)
            if dueno is None:
                self._reservas[clave] = agent_id
            elif dueno != agent_id:
                registrador.debug("t=%03d | %s no reserva %s: ya es de %s", t, agent_id, celda, dueno)

    def reservas(self, excepto: str | None = None) -> dict[tuple[Celda, int], str]:
        """Tabla {(celda, tick): agent_id} sin las reservas de `excepto`."""
        return {clave: dueno for clave, dueno in self._reservas.items() if dueno != excepto}

    def nuevo_tick(self, tick: int) -> None:
        """Inicio de un tick: olvida las reservas de ticks pasados."""
        self._reservas = {clave: dueno for clave, dueno in self._reservas.items() if clave[1] >= tick}

    # -------------------------------------------------------------- azar y tiempo

    def azar(self, fuente: str) -> random.Random:
        """Un generador por fuente, derivado de la seed: agregar una fuente no cambia las demás (§8)."""
        if fuente not in self._azar:
            self._azar[fuente] = random.Random(f"{self.config.seed}-{fuente}")
        return self._azar[fuente]

    def duracion(self, cantidad: int, tasa: int) -> int:
        """ceil(cantidad / tasa) (mínimo 1) más el extra aleatorio U{0..duracion_extra_maxima}.
        Con extra 0 no llama al generador (la línea base no cambia)."""
        base = duracion_ticks(cantidad, tasa)
        extra = self.config.incertidumbre["duracion_extra_maxima"]
        if extra > 0:
            base += self.azar("duracion").randint(0, extra)
        return base

    # ---------------------------------------------------------------- grano

    def grano_cosechado(self) -> int:
        """Devuelve el total histórico de grano retirado del campo."""
        return sum(self._cosechadas.values())

    def cosechar(self, agent_id: str, celda: Celda) -> int:
        """Cosecha una celda válida una sola vez, respetando la capacidad. Devuelve el grano obtenido."""
        agente = self._agentes[agent_id]
        celda = tuple(celda)

        if not agent_id.startswith("cosechadora_"):
            raise ValueError("solo las cosechadoras pueden cosechar")
        if celda not in self._celdas_campo:
            raise ValueError(f"celda fuera del campo: {celda}")
        if celda in self._cosechadas:
            raise ValueError(f"celda ya cosechada: {celda}")
        if agente.posicion != celda:
            raise ValueError(f"la cosechadora no está en {celda}")

        cantidad = self.rendimiento(celda)
        if agente.carga + cantidad > agente.capacidad:
            raise ValueError("capacidad insuficiente para cosechar la celda")

        agente.carga += cantidad
        self._cosechadas[celda] = cantidad

        self._eventos.append({
            "tipo": "CELDA_COSECHADA",
            "celda": list(celda),
            "agente": agent_id,
            "cantidad": cantidad,
        })

        return cantidad

    def cosechada(self, celda: Celda) -> bool:
        return tuple(celda) in self._cosechadas

    def transferir(self, de: str, a: str, cantidad: int) -> int:
        """Transfiere grano de forma atómica entre agentes vecinos."""
        origen = self._agentes[de]
        destino = self._agentes[a]

        if type(cantidad) is not int or cantidad < 0:
            raise ValueError("cantidad debe ser un entero no negativo")

        x1, y1 = origen.posicion
        x2, y2 = destino.posicion

        if abs(x1 - x2) + abs(y1 - y2) != 1:
            raise ValueError("la transferencia requiere agentes vecinos")

        espacio_libre = max(0, destino.capacidad - destino.carga)
        transferido = min(cantidad, origen.carga, espacio_libre)

        origen.carga -= transferido
        destino.carga += transferido

        return transferido

    def depositar(self, agent_id: str) -> int:
        """Mueve el grano de un carro situado en la bodega al total entregado."""
        agente = self._agentes[agent_id]

        if not agent_id.startswith("carro_"):
            raise ValueError("solo los carros pueden depositar grano")
        if agente.posicion != self.bodega:
            raise ValueError("el carro debe estar en la bodega para depositar")

        cantidad = agente.carga
        agente.carga = 0
        self.entregado += cantidad

        self._eventos.append({
            "tipo": "DEPOSITO",
            "agente": agent_id,
            "cantidad": cantidad,
            "entregado_total": self.entregado,
        })

        return cantidad

    # ------------------------------------------------------------- combustible

    def combustible_para(self, agent_id: str, celdas: int, ticks_encendido: int) -> float:
        """Litros estimados para recorrer `celdas` y estar `ticks_encendido` ticks quieto con el motor
        encendido (los agentes lo usan para respetar la reserva, §9)."""
        comb = self.config.combustible
        return (celdas * comb[f"consumo_por_celda_{self._tipo(agent_id)}"]
                + ticks_encendido * comb["consumo_por_tick_encendido"])

    def actualizar_combustible(self, agente, se_movio: bool) -> None:
        """Después del paso de cada agente (§9): consumo por celda o por tick encendido y recarga en su
        base con el motor apagado. Nunca negativo (R11)."""
        if getattr(agente, "combustible", None) is None:
            return
        comb = self.config.combustible
        estado = _texto(agente.estado)
        if se_movio:
            gasto = comb[f"consumo_por_celda_{self._tipo(agente.agent_id)}"]
        elif estado not in APAGADO:
            gasto = comb["consumo_por_tick_encendido"]
        else:
            gasto = 0.0
        nivel = round(agente.combustible - gasto, 2)
        if nivel <= 0:
            if nivel < 0 or gasto:
                registrador.warning("%s se quedó sin combustible (revisa la configuración)", agente.agent_id)
            nivel = 0.0
        agente.combustible = nivel

        en_base = agente.posicion == self.base_de(agente.agent_id)
        if en_base and estado in APAGADO and agente.combustible < agente.tanque:
            faltante = agente.tanque - agente.combustible
            tasa = comb["tasa_recarga"]
            cantidad = round(faltante if tasa == 0 else min(tasa, faltante), 2)
            agente.combustible = round(agente.combustible + cantidad, 2)
            self._eventos.append({
                "tipo": "RECARGA",
                "agente": agente.agent_id,
                "cantidad": cantidad,
                "nivel": agente.combustible,
            })

    # ------------------------------------------------------------------ eventos

    def registrar_bloqueo(self, agent_id: str) -> None:
        """Registra que un agente no pudo ejecutar un movimiento previsto."""
        if agent_id not in self._agentes:
            raise ValueError(f"agente no registrado: {agent_id}")

        self._eventos.append({
            "tipo": "BLOQUEO",
            "agente": agent_id,
        })

    def registrar_restriccion(self, agent_id: str, regla: str, detalle: str) -> None:
        """Una regla de seguridad cambió una decisión del agente (§10, IEEE 7007)."""
        if agent_id not in self._agentes:
            raise ValueError(f"agente no registrado: {agent_id}")
        if regla not in REGLAS_RESTRICCION:
            raise ValueError(f"regla desconocida: {regla}")
        self._eventos.append({
            "tipo": "RESTRICCION",
            "agente": agent_id,
            "regla": regla,
            "detalle": detalle,
        })

    def drenar_eventos(self) -> list[dict]:
        """Entrega los eventos acumulados y vacía la lista interna."""
        eventos = self._eventos
        self._eventos = []
        return eventos

    def descripcion(self) -> dict:
        """Datos estáticos del mundo para el trace. La matriz `rendimiento` (alto × ancho, 0 en servicio
        y obstáculos) va solo si alguna celda da distinto de `grano_por_celda`."""
        descripcion = self._descripcion_sin_rendimiento()
        if any(v != self.grano_por_celda for v in self._rendimiento.values()):
            descripcion["rendimiento"] = [
                [self._rendimiento.get((x, y), 0) for x in range(self.ancho)] for y in range(self.alto)
            ]
        return descripcion


def duracion_ticks(cantidad: int, tasa: int) -> int:
    """Calcula ceil(cantidad / tasa), con un mínimo de un tick."""
    if type(cantidad) is not int or cantidad < 0:
        raise ValueError("cantidad debe ser un entero no negativo")
    if type(tasa) is not int or tasa <= 0:
        raise ValueError("tasa debe ser un entero positivo")

    return max(1, (cantidad + tasa - 1) // tasa)
