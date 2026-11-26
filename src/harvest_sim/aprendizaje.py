"""Despacho aprendido (mejora M1): Q-learning tabular y SARSA para decidir cuándo pedir carro.  [Joel]

Especificación: docs/plan_terreno.md §M1 y docs/especificacion_mejoras.md §M1.

Con `politica.aviso = "qlearning"` (y asignación por subasta), la cosechadora ya no pide carro al pasar un
umbral fijo: cada vez que su tolva entra a un tramo nuevo (sin servicio en curso) le pregunta al
`Despachador` si pide carro o sigue cosechando. Lo escribió el equipo, sin librerías de aprendizaje (es lo que pide la materia).

- **Estado** (`estado_de`): tramo de la tolva (0–4; 5 = llena), carros libres (0, 1, 2 o más), tramo de la
  distancia al carro más cercano (0–3, relativa al tamaño del campo) y si otra cosechadora ya pidió carro.
- **Acciones:** 0 = seguir cosechando, 1 = pedir carro.
- **Recompensa:** −1 por cada tick que la cosechadora pasa llena esperando y −`costo_solicitud` por cada
  llamada. **Cliff:** −`castigo_cliff` si la tolva se llena sin carro en camino (la llamada se hace a la
  fuerza, como en la línea base).
- **Decisiones como semi-MDP:** la recompensa se acumula entre una decisión y la siguiente de la misma
  cosechadora; al final de la corrida se cierra la última transición (sin valor futuro).
- **Actualización:** Q-learning, Q(s,a) += α·(r + γ·max Q(s',·) − Q(s,a)); SARSA usa Q(s',a') con la acción
  que de verdad se tomó.
- **Evaluación:** sin exploración (ε = 0). En un estado que nunca se visitó (las dos Q en 0) o con empate,
  se usa la regla del umbral (`umbral_aviso`), así que lo peor que pasa es portarse como la estrategia
  anticipada.

Determinismo: la exploración usa su propio `random.Random(semilla)`; la misma tabla, el mismo escenario y la
misma seed dan el mismo trace.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

ACCIONES = ("seguir", "pedir")
SEGUIR, PEDIR = 0, 1
ALGORITMOS = ("qlearning", "sarsa")

# Hiperparámetros por defecto (se guardan con la tabla).
PARAMETROS = {"alfa": 0.1, "gamma": 0.999, "epsilon": 0.1, "costo_solicitud": 10.0, "castigo_cliff": 100.0}

CARPETA_TABLAS = Path(__file__).resolve().parents[2] / "config" / "aprendizaje"

ESTADOS_CARRO_LIBRE = frozenset({"EN_BASE", "REGRESANDO_A_BASE"})


def _texto(valor) -> str:
    return getattr(valor, "value", valor)


def estado_de(cosechadora, mundo, llena: bool = False) -> tuple[int, int, int, int]:
    """(tramo de la tolva, carros libres, tramo de distancia, otra pidió) de una cosechadora."""
    tramo = 5 if llena else min(4, int(5 * cosechadora.carga / cosechadora.capacidad))
    carros = [a for a in mundo._agentes if a.startswith("carro_")]
    libres = min(2, sum(1 for c in carros if mundo.estado_de(c) in ESTADOS_CARRO_LIBRE))
    if carros:
        x, y = cosechadora.posicion
        d = min(abs(mundo.posicion(c)[0] - x) + abs(mundo.posicion(c)[1] - y) for c in carros)
        escala = d / max(1, mundo.ancho + mundo.alto)
        distancia = 0 if escala < 0.1 else 1 if escala < 0.25 else 2 if escala < 0.5 else 3
    else:
        distancia = 3
    otra = any(
        a != cosechadora.agent_id and (getattr(ag, "servicio", None) is not None
                                       or getattr(ag, "contratado", None) is not None)
        for a, ag in mundo._agentes.items() if a.startswith("cosechadora_")
    )
    return tramo, libres, distancia, int(otra)


def clave(estado: tuple) -> str:
    return ",".join(str(v) for v in estado)


class Despachador:
    """Tabla Q compartida por las cosechadoras de una corrida (y entre corridas al entrenar)."""

    def __init__(self, algoritmo: str = "qlearning", parametros: dict | None = None, aprender: bool = False,
                 semilla: int = 0, tabla: dict[str, list[float]] | None = None) -> None:
        if algoritmo not in ALGORITMOS:
            raise ValueError(f"algoritmo debe ser uno de {ALGORITMOS}")
        self.algoritmo = algoritmo
        self.parametros = {**PARAMETROS, **(parametros or {})}
        self.aprender = aprender
        self.azar = random.Random(semilla)
        self.q: dict[str, list[float]] = {k: list(v) for k, v in (tabla or {}).items()}
        self.visitas: dict[str, int] = {}
        self._pendiente: dict[str, tuple[str, int, float]] = {}  # cosechadora -> (estado, acción, recompensa)
        self._tramo: dict[str, int | None] = {}  # último tramo de la tolva en que decidió cada cosechadora
        self.recompensa_episodio = 0.0
        self.decisiones = 0
        self.cliffs = 0
        self.respaldo_umbral = 0

    # ------------------------------------------------------------ decisión

    def valores(self, k: str) -> list[float]:
        return self.q.setdefault(k, [0.0, 0.0])

    def _elegir(self, k: str, umbral: bool) -> int:
        if self.aprender and self.azar.random() < self.parametros["epsilon"]:
            return self.azar.randrange(2)
        q = self.q.get(k)
        if q is None or q[SEGUIR] == q[PEDIR]:
            if not self.aprender:
                self.respaldo_umbral += 1
            return PEDIR if umbral else SEGUIR
        return PEDIR if q[PEDIR] > q[SEGUIR] else SEGUIR

    def decidir(self, cosechadora, mundo, umbral: bool) -> bool:
        """True si la cosechadora debe pedir carro ahora. `umbral`: lo que haría la regla fija.

        Solo es una decisión al ENTRAR a un tramo nuevo de la tolva (una vez por tramo y ciclo); en las demás
        celdas sigue cosechando. Con una decisión por celda, pedir una celda más tarde cambia el ocio en
        décimas de tick y esa diferencia se pierde en el ruido de la actualización."""
        estado = estado_de(cosechadora, mundo)
        if self._tramo.get(cosechadora.agent_id) == estado[0]:
            return False
        self._tramo[cosechadora.agent_id] = estado[0]
        k = clave(estado)
        accion = self._elegir(k, umbral)
        self._transicion(cosechadora.agent_id, k, accion)
        if accion == PEDIR:
            self.recompensar(cosechadora.agent_id, -self.parametros["costo_solicitud"])
            self._tramo[cosechadora.agent_id] = None  # el siguiente ciclo vuelve a decidir desde el tramo 0
        self.decisiones += 1
        return accion == PEDIR

    def forzada(self, cosechadora, mundo) -> None:
        """La tolva se llenó sin carro en camino: cliff y llamada obligatoria."""
        self.cliffs += 1
        self.recompensar(cosechadora.agent_id, -self.parametros["castigo_cliff"])
        k = clave(estado_de(cosechadora, mundo, llena=True))
        self._tramo[cosechadora.agent_id] = None
        self._transicion(cosechadora.agent_id, k, PEDIR, forzada=True)
        self.recompensar(cosechadora.agent_id, -self.parametros["costo_solicitud"])

    def recompensar(self, agente: str, r: float) -> None:
        self.recompensa_episodio += r
        if agente in self._pendiente:
            s, a, acumulada = self._pendiente[agente]
            self._pendiente[agente] = (s, a, acumulada + r)

    def tick(self, cosechadoras) -> None:
        """−1 por cada cosechadora llena esperando en este tick."""
        for c in cosechadoras:
            if _texto(c.estado) == "LLENA_ESPERANDO":
                self.recompensar(c.agent_id, -1.0)

    def _transicion(self, agente: str, k: str, accion: int, forzada: bool = False) -> None:
        """Cierra la transición pendiente de `agente` con el estado `k` y abre la nueva. En el estado forzado
        (tolva llena) la única acción posible es pedir, así que Q-learning tampoco toma el máximo: Q(llena,
        seguir) nunca se actualiza y valdría 0, lo que haría gratis el cliff."""
        self.visitas[k] = self.visitas.get(k, 0) + 1
        if self.aprender and agente in self._pendiente:
            s, a, r = self._pendiente[agente]
            siguiente = self.valores(k)
            futuro = siguiente[accion] if self.algoritmo == "sarsa" or forzada else max(siguiente)
            self._actualizar(s, a, r + self.parametros["gamma"] * futuro)
        self._pendiente[agente] = (k, accion, 0.0)

    def _actualizar(self, s: str, a: int, objetivo: float) -> None:
        q = self.valores(s)
        q[a] += self.parametros["alfa"] * (objetivo - q[a])

    def terminar(self) -> None:
        """Cierra las transiciones abiertas al final de la corrida (estado terminal: sin valor futuro)."""
        if self.aprender:
            for s, a, r in self._pendiente.values():
                self._actualizar(s, a, r)
        self._pendiente.clear()

    def nuevo_episodio(self) -> None:
        self._pendiente.clear()
        self._tramo.clear()
        self.recompensa_episodio = 0.0
        self.decisiones = self.cliffs = self.respaldo_umbral = 0

    # ------------------------------------------------------------ archivo

    def a_json(self, **extra) -> dict:
        return {"algoritmo": self.algoritmo, "parametros": self.parametros, **extra,
                "estados": {k: [round(v, 4) for v in self.q[k]] for k in sorted(self.q)},
                "visitas": {k: self.visitas.get(k, 0) for k in sorted(self.q)}}

    def guardar(self, ruta: str | Path, **extra) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(self.a_json(**extra), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return ruta

    @classmethod
    def cargar(cls, ruta: str | Path, aprender: bool = False, semilla: int = 0) -> "Despachador":
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return cls(datos["algoritmo"], datos["parametros"], aprender, semilla, datos["estados"])


def ruta_tabla(politica: dict, nombre_escenario: str) -> Path:
    """La tabla de `politica.qtabla` (relativa a config/) o, si no se da,
    config/aprendizaje/qtabla_<aviso>_<escenario>.json (aviso = qlearning o sarsa)."""
    if politica.get("qtabla"):
        ruta = Path(politica["qtabla"])
        return ruta if ruta.is_absolute() else CARPETA_TABLAS.parent / ruta
    return CARPETA_TABLAS / f"qtabla_{politica['aviso']}_{nombre_escenario}.json"


def despachador_de(config) -> "Despachador | None":
    """El despachador que pide la configuración (None con aviso por umbral). Falla con un mensaje claro si
    la tabla no existe: hay que entrenarla con tools/entrenar_despacho.py."""
    politica = config.politica
    if politica.get("aviso", "umbral") == "umbral":
        return None
    ruta = ruta_tabla(politica, config.nombre)
    if not ruta.is_file():
        raise ValueError(f"no existe la tabla aprendida {ruta}; entrénala con "
                         f"python tools/entrenar_despacho.py config/{config.nombre}.json --algoritmo {politica['aviso']}")
    despachador = Despachador.cargar(ruta)
    if despachador.algoritmo != politica["aviso"]:
        raise ValueError(f"la tabla {ruta.name} es de {despachador.algoritmo}, no de {politica['aviso']}")
    return despachador


def sha256_de(ruta: str | Path) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()
