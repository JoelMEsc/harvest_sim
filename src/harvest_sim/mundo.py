
"""Estado físico del mundo: campo, agentes, grano y eventos.

Especificación: secciones 2, 4.2 y 4.3.
"""

from __future__ import annotations

from .config import Config
from .datos.campo import celdas_de_campo, expandir_obstaculos, grano_esperado
from . import rutas

Celda = tuple[int, int]


class Mundo:
    """Almacena el estado del entorno y centraliza las operaciones con grano."""

    bodega: Celda = (0, 0)

    def __init__(self, config: Config) -> None:
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

        self._obstaculos = expandir_obstaculos(
            config.obstaculos, self.ancho, self.alto
        )
        if self._obstaculos:
            raise ValueError("obstáculos aún no soportados en esta entrega")

        self._agentes = {}
        self._cosechadas: set[Celda] = set()
        self._eventos: list[dict] = []

        self._celdas_campo = celdas_de_campo(self.descripcion())
        self.grano_total = grano_esperado(self.descripcion())

    def registrar(self, agente) -> None:
        """Registra el agente y lo coloca en su base."""
        identificador = agente.agent_id

        if identificador not in self._bases:
            raise ValueError(f"agente desconocido: {identificador}")
        if identificador in self._agentes:
            raise ValueError(f"agente ya registrado: {identificador}")

        agente.posicion = self.base_de(identificador)
        self._agentes[identificador] = agente

    def base_de(self, agent_id: str) -> Celda:
        """Devuelve la base asignada al agente."""
        return self._bases[agent_id]

    def posicion(self, agent_id: str) -> Celda:
        """Consulta la posición actual del agente."""
        return self._agentes[agent_id].posicion

    def estado_de(self, agent_id: str) -> str:
        """Consulta el estado del agente como texto."""
        estado = self._agentes[agent_id].estado
        return getattr(estado, "value", estado)

    def ocupadas(self, excepto: str) -> set[Celda]:
        """Devuelve las posiciones ocupadas por otros agentes."""
        return {
            agente.posicion
            for identificador, agente in self._agentes.items()
            if identificador != excepto
        }

    def bloqueadas_fijas(self, agent_id: str) -> set[Celda]:
        """La bodega está prohibida para las cosechadoras."""
        return {self.bodega} if agent_id.startswith("cosechadora_") else set()

    def camino_serpentina(self) -> list[Celda]:
        """Visita las filas del campo alternando la dirección horizontal."""
        camino = []

        for y in range(1, self.alto):
            columnas = (
                range(self.ancho)
                if y % 2
                else range(self.ancho - 1, -1, -1)
            )
            camino.extend((x, y) for x in columnas)

        return camino

    def vecinos(self, celda: Celda) -> list[Celda]:
        """Obtiene las celdas adyacentes mediante el módulo de rutas."""
        return rutas.vecinos(celda, self.ancho, self.alto)

    def ruta_bfs(
        self, origen: Celda, destino: Celda, bloqueadas: set[Celda]
    ) -> list[Celda] | None:
        """Delega el cálculo de la ruta más corta al módulo de rutas."""
        return rutas.bfs(
            origen, destino, self.ancho, self.alto, bloqueadas
        )

    def grano_cosechado(self) -> int:
        """Devuelve el total histórico de grano retirado del campo."""
        return len(self._cosechadas) * self.grano_por_celda

    def cosechar(self, agent_id: str, celda: Celda) -> int:
        """Cosecha una celda válida una sola vez, respetando la capacidad."""
        agente = self._agentes[agent_id]

        if not agent_id.startswith("cosechadora_"):
            raise ValueError("solo las cosechadoras pueden cosechar")
        if celda not in self._celdas_campo:
            raise ValueError(f"celda fuera del campo: {celda}")
        if celda in self._cosechadas:
            raise ValueError(f"celda ya cosechada: {celda}")
        if agente.posicion != celda:
            raise ValueError(f"la cosechadora no está en {celda}")
        if agente.carga + self.grano_por_celda > agente.capacidad:
            raise ValueError("capacidad insuficiente para cosechar la celda")

        agente.carga += self.grano_por_celda
        self._cosechadas.add(celda)

        self._eventos.append({
            "tipo": "CELDA_COSECHADA",
            "celda": list(celda),
            "agente": agent_id,
        })

        return self.grano_por_celda

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

    def registrar_bloqueo(self, agent_id: str) -> None:
        """Registra que un agente no pudo ejecutar un movimiento previsto."""
        if agent_id not in self._agentes:
            raise ValueError(f"agente no registrado: {agent_id}")

        self._eventos.append({
            "tipo": "BLOQUEO",
            "agente": agent_id,
        })

    def drenar_eventos(self) -> list[dict]:
        """Entrega los eventos acumulados y vacía la lista interna."""
        eventos = self._eventos
        self._eventos = []
        return eventos

    def descripcion(self) -> dict:
        """Datos estáticos del mundo para el trace 2.1."""
        return {
            "ancho": self.ancho,
            "alto": self.alto,
            "bodega": list(self.bodega),
            "bases": {
                identificador: list(celda)
                for identificador, celda in self._bases.items()
            },
            "grano_por_celda": self.grano_por_celda,
            "obstaculos": [list(celda) for celda in self._obstaculos],
        }


def duracion_ticks(cantidad: int, tasa: int) -> int:
    """Calcula ceil(cantidad / tasa), con un mínimo de un tick."""
    if type(cantidad) is not int or cantidad < 0:
        raise ValueError("cantidad debe ser un entero no negativo")
    if type(tasa) is not int or tasa <= 0:
        raise ValueError("tasa debe ser un entero positivo")

    return max(1, (cantidad + tasa - 1) // tasa)
