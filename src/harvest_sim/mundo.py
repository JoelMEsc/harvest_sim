"""Estado físico del mundo: campo, agentes, grano, reservas, azar, combustible y eventos.

Especificación: secciones 2, 4.2 y 4.3 (primera entrega); §3, §4, §5, §8, §9 y §10 de la segunda.
"""

from __future__ import annotations

import logging
import math
import random

from .config import Config
from .datos.campo import celdas_de_campo, expandir_obstaculos, grano_esperado
from .datos.formato import REGLAS_RESTRICCION
from . import rutas
from .mapa import cobertura as cob
from .mapa import dubins

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

        # Mapa real (trace 2.3, docs/especificacion_terreno.md): bodega, bases, obstáculos, caminos, fuera de
        # campo y lotes vienen del mapa. Sin mapa, el mundo rectangular de siempre.
        self.mapa = config.mapa
        self._bases: dict[str, Celda] = {}
        if self.mapa:
            self.bodega = tuple(self.mapa["bodega"])
            bases = [tuple(b) for b in self.mapa["bases"]]
            for indice in range(1, config.num_carros + 1):
                self._bases[f"carro_{indice}"] = bases[indice - 1]
            for indice in range(1, config.num_cosechadoras + 1):
                self._bases[f"cosechadora_{indice}"] = bases[config.num_carros + indice - 1]
            self._lista_obstaculos = [list(c) for c in self.mapa["obstaculos"]]
            self.celdas_camino: frozenset[Celda] = frozenset(tuple(c) for c in self.mapa["caminos"])
            self.fuera_de_campo: frozenset[Celda] = frozenset(tuple(c) for c in self.mapa["fuera_de_campo"])
            self.tamano_celda_m = float(self.mapa["tamano_celda_m"])
        else:
            for indice in range(1, config.num_carros + 1):
                self._bases[f"carro_{indice}"] = (indice, 0)
            for indice in range(1, config.num_cosechadoras + 1):
                self._bases[f"cosechadora_{indice}"] = (config.num_carros + indice, 0)
            self._lista_obstaculos = expandir_obstaculos(config.obstaculos, self.ancho, self.alto)
            self.celdas_camino = frozenset()
            self.fuera_de_campo = frozenset()
            self.tamano_celda_m = None
        self.obstaculos: frozenset[Celda] = frozenset(tuple(c) for c in self._lista_obstaculos)
        # R10 y R12: nadie entra a obstáculos ni sale del predio
        self._fijas_todos: frozenset[Celda] = self.obstaculos | self.fuera_de_campo
        # R13: solo con mapa y la política activada
        self.respetar_cultivo = bool(self.mapa) and bool(config.politica.get("respetar_cultivo", False))
        # Plan de hileras y rutas: cabeceras, pasadas paralelas a las hileras (eje x) y vueltas con radio de giro
        self.hileras = bool(self.mapa) and config.politica.get("movimiento", "celdas") == "hileras"
        self.cabecera: frozenset[Celda] = frozenset()
        self._entradas: dict[Celda, tuple[Celda, str]] = {}  # inicio de pasada -> (celda de entrada, rumbo)
        self._coberturas: dict[str, cob.Cobertura] = {}

        self._agentes = {}
        self._cosechadas: dict[Celda, int] = {}  # celda -> grano obtenido
        self._eventos: list[dict] = []
        self._reservas: dict[tuple[Celda, int], str] = {}
        self._azar: dict[str, random.Random] = {}
        self._caminos: dict[str, list[Celda]] = {}

        descripcion = self._descripcion_sin_rendimiento()
        self._celdas_campo = celdas_de_campo(descripcion)
        # cultivo en pie: baja con cada cosecha (R13 lo usa en cada tick sin recalcularlo)
        self._en_pie: set[Celda] = set(self._celdas_campo)
        self._rendimiento = self._sortear_rendimiento()
        self._franjas = [] if self.mapa else self._calcular_franjas()
        self._zonas = self._calcular_zonas() if self.mapa else {}
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

    def paso_de(self, agent_id: str) -> set[Celda]:
        """Celdas que el agente necesita libres para su traslado en curso (vacío si no se traslada o no lo
        informa). El carro que acompaña a una cosechadora no se detiene en ellas."""
        necesita = getattr(self._agentes[agent_id], "celdas_de_paso", None)
        return necesita(self) if callable(necesita) else set()

    def ocupadas(self, excepto: str) -> set[Celda]:
        """Devuelve las posiciones ocupadas por otros agentes."""
        return {
            agente.posicion
            for identificador, agente in self._agentes.items()
            if identificador != excepto
        }

    def bloqueadas_fijas(self, agent_id: str) -> set[Celda]:
        """Obstáculos (R10) y fuera de campo (R12) para todos; además, la bodega para las cosechadoras (R9)."""
        fijas = set(self._fijas_todos)
        if agent_id.startswith("cosechadora_"):
            fijas.add(self.bodega)
        return fijas

    def bloqueadas_para(self, agent_id: str) -> set[Celda]:
        """Lo que el agente no puede pisar ahora: las fijas y, para los carros con R13 activa, el cultivo en
        pie (docs/especificacion_terreno.md §7). Crece lo transitable conforme hay más rastrojo."""
        fijas = self.bloqueadas_fijas(agent_id)
        if self.respetar_cultivo and agent_id.startswith("carro_"):
            fijas |= self._en_pie
        return fijas

    def cultivo_en_pie(self) -> set[Celda]:
        """Celdas de campo que todavía no se cosechan (no modificar: es el conjunto del mundo)."""
        return self._en_pie

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
            **self._descripcion_mapa(),
        }

    def _descripcion_mapa(self) -> dict:
        """Campos del trace 2.3 (solo con mapa)."""
        if not self.mapa:
            return {}
        return {
            "tamano_celda_m": self.tamano_celda_m,
            "caminos": [list(c) for c in self.mapa["caminos"]],
            "fuera_de_campo": [list(c) for c in self.mapa["fuera_de_campo"]],
            "lotes": {n: [list(c) for c in cs] for n, cs in self.mapa["lotes"].items()},
            **({"altura_m": self.mapa["altura_m"]} if "altura_m" in self.mapa else {}),
            "geo": self.mapa["geo"],
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

    def zonas(self) -> dict[str, list[str]]:
        """Con mapa: los lotes (o partes de lote) de cada cosechadora, en el orden en que los recorre."""
        return {a: [n for n, _ in unidades] for a, unidades in self._zonas.items()}

    def _calcular_zonas(self) -> dict[str, list[tuple[str, list[Celda]]]]:
        """Reparte los lotes completos entre las cosechadoras (el más grande a la que lleva menos celdas). Si
        hay más cosechadoras que lotes, parte el más grande en bandas de filas. Cada unidad se recorre en
        boustrophedon empezando por la orilla que toca un camino (docs/especificacion_terreno.md §9)."""
        m = self.config.num_cosechadoras
        unidades = [(n, {tuple(c) for c in cs} & self._celdas_campo) for n, cs in self.mapa["lotes"].items()]
        unidades = [u for u in unidades if u[1]]
        while len(unidades) < m:
            nombre, celdas = max(unidades, key=lambda u: (len(u[1]), u[0]))
            unidades.remove((nombre, celdas))
            filas = sorted({y for _, y in celdas})
            acumulado, corte = 0, filas[0]
            for y in filas:
                acumulado += sum(1 for c in celdas if c[1] == y)
                corte = y
                if acumulado >= len(celdas) / 2:
                    break
            a = {c for c in celdas if c[1] <= corte}
            b = celdas - a
            if not b:  # una sola fila: se parte por x
                xs = sorted(x for x, _ in celdas)
                a = {c for c in celdas if c[0] <= xs[len(xs) // 2 - 1]}
                b = celdas - a
            unidades += [(f"{nombre}/1", a), (f"{nombre}/2", b)]

        dist = self._distancias_por_camino()
        asignacion = {f"cosechadora_{j}": [] for j in range(1, m + 1)}
        cargas = dict.fromkeys(asignacion, 0)
        for nombre, celdas in sorted(unidades, key=lambda u: (-len(u[1]), u[0])):
            j = min(asignacion, key=lambda a: (cargas[a], int(a.rsplit("_", 1)[1])))
            asignacion[j].append((nombre, celdas))
            cargas[j] += len(celdas)
        zonas = {}
        for agente, lista in asignacion.items():
            lista.sort(key=lambda u: (min(self._a_camino(c, dist) for c in u[1]), u[0]))
            if self.hileras:
                zonas[agente] = [(n, self._cobertura_hileras(n, celdas, dist)) for n, celdas in lista]
            else:
                zonas[agente] = [(n, self._boustrophedon(celdas, dist)) for n, celdas in lista]
        return zonas

    def _distancias_por_camino(self) -> dict[Celda, int]:
        """Distancia (en celdas) de la bodega a cada celda de camino o patio, andando solo por camino."""
        dist = {self.bodega: 0}
        cola = [self.bodega]
        for celda in cola:
            for v in self.vecinos(celda):
                if v in self.celdas_camino and v not in dist:
                    dist[v] = dist[celda] + 1
                    cola.append(v)
        return dist

    def _a_camino(self, celda: Celda, dist: dict[Celda, int]) -> int:
        """Qué tan lejos queda una celda de la bodega por camino: 0 + distancia si toca un camino; si no,
        castigada con la distancia Manhattan al camino más cercano."""
        cerca = [dist[v] for v in self.vecinos(celda) if v in dist]
        if cerca:
            return min(cerca)
        return 10_000 + min(abs(celda[0] - c[0]) + abs(celda[1] - c[1]) for c in dist)

    # ------------------------------------------------------------------ hileras (plan de hileras y rutas)

    def _vuelta_ticks(self, desde: Celda, rumbo_desde: str, hasta: Celda, rumbo_hasta: str) -> int:
        """Ticks de la curva de Dubins entre dos poses de celda (centro y rumbo E/O/N/S), con el radio de giro
        y la velocidad de vuelta de `config.maquinas`. Un tick = una celda a velocidad de cosecha."""
        m = self.config.maquinas
        s = self.tamano_celda_m
        angulo = {"E": 0.0, "S": math.pi / 2, "O": math.pi, "N": 3 * math.pi / 2}
        c = dubins.camino((desde[0] * s, desde[1] * s, angulo[rumbo_desde]),
                          (hasta[0] * s, hasta[1] * s, angulo[rumbo_hasta]), m["radio_giro_m"])
        return math.ceil(c.largo / s * m["velocidad_cosecha_kmh"] / m["velocidad_vuelta_kmh"] - 1e-9)

    def _cobertura_hileras(self, nombre: str, celdas: set[Celda], dist: dict[Celda, int]) -> list[Celda]:
        """Recorrido de una unidad como en la industria: primero la cabecera («abrir el campo»), luego las pasadas
        a lo largo de las hileras en el orden de menor costo de vueltas (snake o boustrophedon), y cada pasada se
        entra desde su celda de cabecera, de frente."""
        k = cob.celdas_de_cabecera(self.config.maquinas["radio_giro_m"], self.tamano_celda_m)
        entrada = min(celdas, key=lambda c: (self._a_camino(c, dist), c))

        r = cob.cobertura(celdas, k, desde=entrada, vuelta=self._vuelta_ticks)
        self._coberturas[nombre] = r
        self.cabecera = self.cabecera | frozenset(r.cabecera)
        # se arranca desde el camino que toca la unidad (o desde su primera celda si no toca ninguno)
        transitables = set(self.celdas_camino)
        junto = [v for v in self.vecinos(entrada) if v in transitables]
        inicio = min(junto) if junto else entrada
        recorrido, entradas, sin_alcance = cob.secuencia_alcanzable(r, inicio, transitables)
        if sin_alcance:
            registrador.warning("unidad %s: %d celdas no se alcanzan sin cruzar cultivo", nombre, sin_alcance)
        self._entradas.update(entradas)
        return recorrido

    def costos_de_giro(self, carro: bool = False) -> tuple[int, int]:
        """(giro de 90°, media vuelta en K) en ticks extra para el A* con rumbo de los traslados. 90°: el cuarto de
        circunferencia (πR/2) a su velocidad, en ticks (un tick = una celda a velocidad de cosecha), menos el tick
        de avance; la vuelta en K, dos de ellos. El carro usa su propio radio y su velocidad."""
        m = self.config.maquinas
        if carro:
            radio, velocidad = m["radio_giro_carro_m"], m["velocidad_carro_kmh"]
        else:
            radio, velocidad = m["radio_giro_m"], m["velocidad_vuelta_kmh"]
        cuarto = math.pi * radio / 2 / self.tamano_celda_m * m["velocidad_cosecha_kmh"] / velocidad
        giro90 = max(0, math.ceil(cuarto - 1e-9) - 1)
        return giro90, 2 * (giro90 + 1)

    def planear_con_rumbo(self, origen: Celda, rumbo: str, destino: Celda, tick: int, bloqueadas: set[Celda],
                          reservas, horizonte: int = rutas.HORIZONTE, permanencia: int | None = None,
                          carro: bool = False):
        """Con hileras, los traslados usan A* con rumbo (el giro cuesta tiempo); sin hileras, el BFS de siempre."""
        if not self.hileras:
            return rutas.bfs_tiempo(origen, destino, tick, self.ancho, self.alto, bloqueadas, reservas, horizonte,
                                    permanencia)
        giro90, giro180 = self.costos_de_giro(carro=carro)
        return rutas.astar_rumbo_tiempo(origen, rumbo, destino, tick, self.ancho, self.alto, bloqueadas, reservas,
                                        giro90, giro180, horizonte, permanencia)

    def trayectoria_de_vuelta(self, desde: Celda, rumbo_desde: str, celda: Celda, paso_m: float = 2.0) -> list[list[float]]:
        """La curva de Dubins de la vuelta hacia la pasada que empieza en `celda`, muestreada cada `paso_m` metros:
        [x, y, rumbo] en metros del marco de la cuadrícula (para el evento TRAYECTORIA del trace 2.4)."""
        entrada = self._entradas.get(celda)
        if entrada is None:
            return []
        s = self.tamano_celda_m
        angulo = {"E": 0.0, "S": math.pi / 2, "O": math.pi, "N": 3 * math.pi / 2}
        c = dubins.camino((desde[0] * s, desde[1] * s, angulo[rumbo_desde]),
                          (celda[0] * s, celda[1] * s, angulo[entrada[1]]), self.config.maquinas["radio_giro_m"])
        return [[round(x, 3), round(y, 3), round(t, 4)] for x, y, t in c.muestrear(paso_m)]

    def es_vuelta_de_cabecera(self, desde: Celda, celda: Celda) -> bool:
        """¿Ir de `desde` al inicio de pasada `celda` es una vuelta de cabecera? Sí si sale del fin de una pasada (no
        de la cabecera) hacia otra a pocas filas y dentro del ancho de la cabecera; un traslado largo no es vuelta
        (su ruta la decide el A* por rastrojo, no una curva que cruzaría el cultivo)."""
        if celda not in self._entradas or desde in self.cabecera:
            return False
        k = cob.celdas_de_cabecera(self.config.maquinas["radio_giro_m"], self.tamano_celda_m)
        return abs(celda[1] - desde[1]) <= 3 and abs(celda[0] - desde[0]) <= 2 * k + 1

    def registrar_trayectoria(self, agent_id: str, tramo: str, puntos: list, ticks: int) -> None:
        """2.4: deja en el log la geometría de una vuelta (evento TRAYECTORIA)."""
        if agent_id not in self._agentes:
            raise ValueError(f"agente no registrado: {agent_id}")
        self._eventos.append({"tipo": "TRAYECTORIA", "agente": agent_id, "tramo": tramo, "puntos": puntos,
                              "ticks": ticks})

    def entrada_de_pasada(self, celda: Celda) -> tuple[Celda, str] | None:
        """Si `celda` es el inicio de una pasada (con hileras): la celda de cabecera desde la que se entra y el
        rumbo de la pasada. R14: a una pasada se entra de frente, a lo largo de las hileras, nunca de lado."""
        return self._entradas.get(celda)

    def ticks_de_vuelta(self, desde: Celda, rumbo_desde: str, celda: Celda) -> int:
        """Ticks que toma llegar de `desde` (con su rumbo) al inicio de la pasada `celda`, según Dubins."""
        entrada = self._entradas.get(celda)
        if entrada is None or not self.hileras:
            return 0
        return self._vuelta_ticks(desde, rumbo_desde, celda, entrada[1])

    def _boustrophedon(self, celdas: set[Celda], dist: dict[Celda, int]) -> list[Celda]:
        """Orden de cosecha de una unidad: una fila es una pasada. Empieza en la fila de una orilla y en el
        extremo más cercano a un camino; cada fila siguiente, en el extremo más cercano al final de la
        anterior."""
        filas = sorted({y for _, y in celdas})
        por_fila = {y: sorted(x for x, yy in celdas if yy == y) for y in filas}
        opciones = []
        for orden in (filas, filas[::-1]):
            primera = por_fila[orden[0]]
            for inicio_x in (primera[0], primera[-1]):
                opciones.append((self._a_camino((inicio_x, orden[0]), dist), orden == filas, inicio_x, orden))
        _, _, inicio_x, orden = min(opciones, key=lambda o: (o[0], not o[1], o[2]))
        recorrido: list[Celda] = []
        for y in orden:
            xs = por_fila[y]
            if not recorrido:
                fila = xs if inicio_x == xs[0] else xs[::-1]
            else:
                ux, uy = recorrido[-1]
                ida = abs(xs[0] - ux) + abs(y - uy)
                vuelta = abs(xs[-1] - ux) + abs(y - uy)
                fila = xs if ida <= vuelta else xs[::-1]
            recorrido.extend((x, y) for x in fila)
        return recorrido

    def camino(self, agent_id: str) -> list[Celda]:
        """Serpentina de la franja de esa cosechadora, sin obstáculos. Paridad global (fila impar:
        x creciente), así que con una cosechadora y sin obstáculos es la serpentina de v0.1."""
        if agent_id not in self._caminos and self.mapa:
            if agent_id not in self._zonas:
                raise KeyError(agent_id)
            self._caminos[agent_id] = [c for _, recorrido in self._zonas[agent_id] for c in recorrido]
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
            origen, destino, self.ancho, self.alto, set(bloqueadas) | self._fijas_todos
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
        self._en_pie.discard(celda)

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

    def altura(self, celda: Celda) -> float | None:
        """Altura de la celda en metros (relieve del mapa) o None si el mundo no tiene relieve."""
        alturas = (self.mapa or {}).get("altura_m")
        if alturas is None:
            return None
        return alturas[celda[1]][celda[0]]

    def factor_pendiente(self, desde: Celda | None, hasta: Celda) -> float:
        """Multiplicador del consumo por celda al moverse de `desde` a `hasta`: 1 + f · pendiente_% / 100 al
        subir, 1 al bajar o en plano (docs/especificacion_terreno.md §8). 1 sin relieve o con f = 0."""
        f = self.config.combustible.get("factor_pendiente", 0.0)
        if not f or desde is None or self.tamano_celda_m is None:
            return 1.0
        h0, h1 = self.altura(desde), self.altura(hasta)
        if h0 is None or h1 is None or h1 <= h0:
            return 1.0
        return 1.0 + f * (h1 - h0) / self.tamano_celda_m

    def actualizar_combustible(self, agente, se_movio: bool, desde: Celda | None = None) -> None:
        """Después del paso de cada agente (§9): consumo por celda o por tick encendido y recarga en su
        base con el motor apagado. Nunca negativo (R11)."""
        if getattr(agente, "combustible", None) is None:
            return
        comb = self.config.combustible
        estado = _texto(agente.estado)
        if se_movio:
            gasto = comb[f"consumo_por_celda_{self._tipo(agente.agent_id)}"] * \
                self.factor_pendiente(desde, agente.posicion)
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

    def registrar_decision(self, evento: dict) -> None:
        """M1: una decisión del despacho aprendido (evento DECISION_DESPACHO; la arma aprendizaje.py)."""
        if evento.get("agente") not in self._agentes:
            raise ValueError(f"agente no registrado: {evento.get('agente')}")
        self._eventos.append({"tipo": "DECISION_DESPACHO", **evento})

    def drenar_eventos(self) -> list[dict]:
        """Entrega los eventos acumulados y vacía la lista interna."""
        eventos = self._eventos
        self._eventos = []
        return eventos

    def descripcion(self) -> dict:
        """Datos estáticos del mundo para el trace. La matriz `rendimiento` (alto × ancho, 0 en servicio
        y obstáculos) va solo si alguna celda da distinto de `grano_por_celda`."""
        descripcion = self._descripcion_sin_rendimiento()
        if self.hileras and self._coberturas:
            # 2.4: cabecera y pasadas (tramos de fila a lo largo de las hileras) para el visor y Unity
            descripcion["cabecera"] = [list(c) for c in sorted(self.cabecera, key=lambda c: (c[1], c[0]))]
            descripcion["pasadas"] = sorted([p.x0, p.y, p.x1] for r in self._coberturas.values() for p in r.pasadas)
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
