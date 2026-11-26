"""Curvas de Dubins: el camino más corto, solo hacia adelante y con radio de giro mínimo R.  [Joel]

Plan de hileras y rutas (fase H2). Es lo que usa el planificador de trayectorias de Fields2Cover (`PP_Dubins`)
para unir el fin de una pasada con el inicio de la siguiente. Dubins (1957) mostró que el camino más corto entre
dos poses (x, y, rumbo) para un vehículo que solo avanza y gira con radio >= R es una de seis palabras:
LSL, RSR, LSR, RSL, RLR y LRL (L = arco a la izquierda, R = arco a la derecha, S = recta). Las fórmulas son las
de Shkel y Lumelsky (2001), en coordenadas normalizadas por R.

Además clasifica la vuelta entre dos pasadas paralelas como la literatura de cabeceras: U si la separación
d >= 2R (cabe una media vuelta con recta), Ω si d < 2R (hay que abrirse hacia el lado contrario).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Pose = tuple[float, float, float]  # (x, y, rumbo en radianes, 0 = +x, sentido antihorario)
PALABRAS = ("LSL", "RSR", "LSR", "RSL", "RLR", "LRL")


def _mod2pi(a: float) -> float:
    return a % (2 * math.pi)


@dataclass(frozen=True)
class Dubins:
    inicio: Pose
    radio: float
    palabra: str
    tramos: tuple[float, float, float]  # largos normalizados (ángulo en radianes para arcos, distancia/R para S)

    @property
    def largo(self) -> float:
        return sum(self.tramos) * self.radio

    def muestrear(self, paso: float) -> list[Pose]:
        """Poses cada `paso` metros a lo largo del camino (incluye el inicio y el final)."""
        x, y, th = self.inicio
        poses = [(x, y, th)]
        restante = 0.0
        for letra, t in zip(self.palabra, self.tramos):
            largo = t * self.radio
            avanzado = 0.0
            while avanzado < largo - 1e-9:
                d = min(paso - restante, largo - avanzado)
                x, y, th = _avanzar((x, y, th), letra, d, self.radio)
                avanzado += d
                restante += d
                if restante >= paso - 1e-9:
                    poses.append((x, y, th))
                    restante = 0.0
        if poses[-1] != (x, y, th):
            poses.append((x, y, th))
        return poses


def _avanzar(pose: Pose, letra: str, d: float, r: float) -> Pose:
    x, y, th = pose
    if letra == "S":
        return x + d * math.cos(th), y + d * math.sin(th), th
    giro = d / r if letra == "L" else -d / r
    nuevo = th + giro
    if letra == "L":
        return x + r * (math.sin(nuevo) - math.sin(th)), y - r * (math.cos(nuevo) - math.cos(th)), _mod2pi(nuevo)
    return x - r * (math.sin(nuevo) - math.sin(th)), y + r * (math.cos(nuevo) - math.cos(th)), _mod2pi(nuevo)


def _candidatos(alfa: float, beta: float, d: float) -> dict[str, tuple[float, float, float] | None]:
    sa, sb, ca, cb = math.sin(alfa), math.sin(beta), math.cos(alfa), math.cos(beta)
    cab = math.cos(alfa - beta)
    res: dict[str, tuple[float, float, float] | None] = {}
    # LSL
    p2 = 2 + d * d - 2 * cab + 2 * d * (sa - sb)
    if p2 >= 0:
        tmp = math.atan2(cb - ca, d + sa - sb)
        res["LSL"] = (_mod2pi(-alfa + tmp), math.sqrt(p2), _mod2pi(beta - tmp))
    # RSR
    p2 = 2 + d * d - 2 * cab + 2 * d * (sb - sa)
    if p2 >= 0:
        tmp = math.atan2(ca - cb, d - sa + sb)
        res["RSR"] = (_mod2pi(alfa - tmp), math.sqrt(p2), _mod2pi(-beta + tmp))
    # LSR
    p2 = -2 + d * d + 2 * cab + 2 * d * (sa + sb)
    if p2 >= 0:
        p = math.sqrt(p2)
        tmp = math.atan2(-ca - cb, d + sa + sb) - math.atan2(-2.0, p)
        res["LSR"] = (_mod2pi(-alfa + tmp), p, _mod2pi(-_mod2pi(beta) + tmp))
    # RSL
    p2 = -2 + d * d + 2 * cab - 2 * d * (sa + sb)
    if p2 >= 0:
        p = math.sqrt(p2)
        tmp = math.atan2(ca + cb, d - sa - sb) - math.atan2(2.0, p)
        res["RSL"] = (_mod2pi(alfa - tmp), p, _mod2pi(beta - tmp))
    # RLR
    tmp = (6 - d * d + 2 * cab + 2 * d * (sa - sb)) / 8
    if abs(tmp) <= 1:
        p = _mod2pi(2 * math.pi - math.acos(tmp))
        t = _mod2pi(alfa - math.atan2(ca - cb, d - sa + sb) + p / 2)
        res["RLR"] = (t, p, _mod2pi(alfa - beta - t + p))
    # LRL
    tmp = (6 - d * d + 2 * cab + 2 * d * (sb - sa)) / 8
    if abs(tmp) <= 1:
        p = _mod2pi(2 * math.pi - math.acos(tmp))
        t = _mod2pi(-alfa - math.atan2(ca - cb, d + sa - sb) + p / 2)
        res["LRL"] = (t, p, _mod2pi(-alfa + beta + p))
    return res


def camino(inicio: Pose, fin: Pose, radio: float) -> Dubins:
    """El camino de Dubins más corto de `inicio` a `fin` con radio mínimo `radio`."""
    if radio <= 0:
        raise ValueError("el radio de giro debe ser > 0")
    dx, dy = fin[0] - inicio[0], fin[1] - inicio[1]
    d = math.hypot(dx, dy) / radio
    theta = _mod2pi(math.atan2(dy, dx)) if d > 0 else 0.0
    alfa, beta = _mod2pi(inicio[2] - theta), _mod2pi(fin[2] - theta)
    mejores = [(sum(t), palabra, t) for palabra, t in _candidatos(alfa, beta, d).items() if t is not None]
    _, palabra, tramos = min(mejores, key=lambda m: (round(m[0], 9), PALABRAS.index(m[1])))
    return Dubins(inicio, radio, palabra, tramos)


def tipo_de_vuelta(separacion_m: float, radio: float) -> str:
    """U si la separación entre pasadas alcanza para media vuelta (d >= 2R); si no, Ω."""
    return "U" if separacion_m >= 2 * radio - 1e-9 else "Ω"
