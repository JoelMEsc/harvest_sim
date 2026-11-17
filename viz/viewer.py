"""Visor independiente del trace 2.1 (§7.1); no importa la simulación.

Espacio: pausa; flechas: paso; Inicio/Fin: extremos; +/-: velocidad.
--guardar-cuadros exporta PNG sin ventana cada --cada ticks, incluido el final.
"""
from __future__ import annotations

import argparse
from collections import deque
import json
import os
from pathlib import Path
import sys
import textwrap

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

FONDO = "#f5f3e9"
TEXTO = "#20372d"
CULTIVO = "#dbbd57"
COSECHADO = "#e6e4d6"
COLORES = ("#267449", "#256eab", "#a34e28", "#745ba6")


class Reproductor:
    """Conserva el estado entre ticks dispersos; retroceder reconstruye desde 0."""

    def __init__(self, trace):
        if trace.get("schema_version") != "2.1":
            raise ValueError("se requiere un trace con schema_version 2.1")
        self.trace = trace
        self.total = trace["meta"]["total_ticks"]
        if type(self.total) is not int or self.total < 0:
            raise ValueError("total_ticks debe ser un entero no negativo")
        mundo = trace["mundo"]
        if any(type(mundo[k]) is not int or mundo[k] <= 0 for k in ("ancho", "alto")):
            raise ValueError("el mapa debe tener dimensiones enteras positivas")
        if any(a["capacidad"] <= 0 for a in trace["agentes"]):
            raise ValueError("las capacidades deben ser positivas")
        self.cambios = {}
        anterior = -1
        for entrada in trace["ticks"]:
            tick = entrada["tick"]
            if type(tick) is not int or not anterior < tick <= self.total:
                raise ValueError("los ticks deben ser únicos, crecientes y estar dentro de total_ticks")
            self.cambios[tick] = entrada["cambios"]
            anterior = tick
        if 0 not in self.cambios:
            raise ValueError("falta el estado inicial del tick 0")
        self.reiniciar()
        self.ir_a(0)

    def reiniciar(self):
        self.tick = -1
        self.agentes = {}
        self.cosechadas = set()
        self.entregado = 0
        self.mensajes = []
        self.estelas = {}

    def ir_a(self, destino):
        destino = max(0, min(self.total, destino))
        if destino < self.tick:
            self.reiniciar()
        for tick in range(self.tick + 1, destino + 1):
            self.mensajes = []
            for evento in self.cambios.get(tick, []):
                tipo = evento["tipo"]
                if tipo == "AGENTE":
                    self.agentes.setdefault(evento["id"], {}).update(evento["set"])
                elif tipo == "CELDA_COSECHADA":
                    self.cosechadas.add(tuple(evento["celda"]))
                elif tipo == "DEPOSITO":
                    self.entregado = evento["entregado_total"]
                elif tipo == "MENSAJE_ENVIADO":
                    self.mensajes.append(evento)
            for ident, agente in self.agentes.items():
                pose = agente["pose"]
                self.estelas.setdefault(ident, deque(maxlen=12)).append((pose["x"], pose["y"]))
            self.tick = tick


def dibujar(rep, velocidad=8, pausa=True):
    """Devuelve un Surface para la ventana y la exportación PNG."""
    pygame.font.init()
    mundo = rep.trace["mundo"]
    ancho, alto = mundo["ancho"], mundo["alto"]
    celda = max(2, min(58, 650 // max(ancho, alto)))
    mapa_w, mapa_h = ancho * celda, alto * celda
    panel_x = max(480, mapa_w + 56)
    catalogo = rep.trace["agentes"]
    my = max(370, 140 + len(catalogo) * 105)
    lineas = []
    for e in rep.mensajes:
        mensaje = f"#{e['id']} {e['tipo_mensaje']} ({e.get('performativa', '')}) {e['de']} -> {e['a']} | entrega t={e['entrega_en']} | {e['payload']}"
        lineas.extend(textwrap.wrap(mensaje, 43))
    lineas = lineas or ["Sin envíos en este tick."]
    superficie = pygame.Surface((panel_x + 420, max(620, mapa_h + 280, my + 70 + len(lineas) * 23)))
    superficie.fill(FONDO)
    fuente = pygame.font.Font(None, 23)
    titulo = pygame.font.Font(None, 35)

    def texto(cadena, x, y, grande=False):
        superficie.blit((titulo if grande else fuente).render(str(cadena), True, TEXTO), (x, y))

    def centro(pos):
        return (28 + int((pos[0] + .5) * celda), 120 + int((pos[1] + .5) * celda))

    texto("HARVEST / Reproducción", 28, 24, True)
    texto(rep.trace["meta"]["escenario"], 28, 65)
    texto(f"Tick {rep.tick} / {rep.total}   ·   {'Pausa' if pausa else 'Reproduciendo'}   ·   {velocidad:g} ticks/s", 28, 90)
    obstaculos = {tuple(p) for p in mundo.get("obstaculos", [])}
    bases = {tuple(p) for p in mundo["bases"].values()}
    for y in range(alto):
        for x in range(ancho):
            pos = (x, y)
            color = "#cdd8dc" if y == 0 else COSECHADO if pos in rep.cosechadas else CULTIVO
            rect = pygame.Rect(28 + x * celda, 120 + y * celda, celda, celda)
            pygame.draw.rect(superficie, color, rect)
            pygame.draw.rect(superficie, "white", rect, 1)
            if pos in bases:
                pygame.draw.rect(superficie, "#617b86", rect.inflate(-4, -4), 2)
            if pos == tuple(mundo["bodega"]):
                pygame.draw.rect(superficie, TEXTO, rect.inflate(-4, -4))
                superficie.blit(fuente.render("B", True, "white"), rect.move(6, 5))
            if pos in obstaculos:
                pygame.draw.rect(superficie, "#6a6c68", rect.inflate(-2, -2))
                pygame.draw.line(superficie, "white", rect.topleft, rect.bottomright, 2)
                pygame.draw.line(superficie, "white", rect.topright, rect.bottomleft, 2)
    for i, entrada in enumerate(catalogo):
        ident = entrada["id"]
        agente = rep.agentes.get(ident)
        if not agente:
            continue
        color = COLORES[i % len(COLORES)]
        estela = [centro(p) for p in rep.estelas[ident]]
        if len(estela) > 1:
            pygame.draw.lines(superficie, color, False, estela, 2)
        pose = agente["pose"]
        cx, cy = centro((pose["x"], pose["y"]))
        dx, dy = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "O": (-1, 0)}[pose["orientacion"]]
        r = max(2, celda // 3)
        puntos = [(cx + dx * r, cy + dy * r),
                  (cx - dx * r // 2 - dy * r // 2, cy - dy * r // 2 + dx * r // 2),
                  (cx - dx * r // 2 + dy * r // 2, cy - dy * r // 2 - dx * r // 2)]
        pygame.draw.polygon(superficie, color, puntos)
        pygame.draw.polygon(superficie, "white", puntos, 1)
        py = 125 + i * 105
        pygame.draw.circle(superficie, color, (panel_x + 6, py + 8), 6)
        texto(ident, panel_x + 22, py)
        texto(agente["estado"], panel_x, py + 25)
        carga, capacidad = agente["carga"], entrada["capacidad"]
        texto(f"Carga: {carga} / {capacidad} u. de grano", panel_x, py + 48)
        pygame.draw.rect(superficie, "#d8dfd7", (panel_x, py + 74, 360, 9))
        pygame.draw.rect(superficie, color, (panel_x, py + 74, round(360 * min(1, max(0, carga / capacidad))), 9))
    texto(f"Bodega: {rep.entregado} u. de grano", panel_x, 80)
    ly = 140 + mapa_h
    for i, (color, etiqueta) in enumerate(((CULTIVO, "Por cosechar"), (COSECHADO, "Cosechada"), ("#cdd8dc", "Servicio / bases"), ("#6a6c68", "Obstáculo (X)"))):
        x, y = 28 + (i % 2) * 220, ly + (i // 2) * 27
        pygame.draw.rect(superficie, color, (x, y, 14, 14))
        texto(etiqueta, x + 22, y)
    texto("Espacio: pausa   Flechas: paso   Inicio / Fin", 28, ly + 65)
    texto("+ / -: velocidad   Esc: salir   B: bodega", 28, ly + 91)
    texto("Mensajes del tick", panel_x, my, True)
    for i, linea in enumerate(lineas):
        texto(linea, panel_x, my + 42 + i * 23)
    return superficie


def guardar_cuadros(rep, carpeta, cada=10):
    if cada <= 0:
        raise ValueError("--cada debe ser positivo")
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for tick in sorted(set(range(0, rep.total + 1, cada)) | {rep.total}):
        rep.ir_a(tick)
        ruta = carpeta / f"tick_{tick:06d}.png"
        pygame.image.save(dibujar(rep), ruta)
        rutas.append(ruta)
    # Una reexportación debe mostrar solo los cuadros de la corrida actual.
    for anterior in carpeta.glob("tick_*.png"):
        if anterior.stem[5:].isdigit() and anterior not in rutas:
            anterior.unlink()
    return rutas


def reproducir(rep):
    pygame.display.init()
    pygame.display.set_caption("Harvest Sim · Visor de trace 2.1")
    ventana = pygame.display.set_mode(dibujar(rep).get_size(), pygame.RESIZABLE)
    reloj = pygame.time.Clock()
    pausa, acumulado, velocidad = True, 0.0, 8.0
    while True:
        segundos = reloj.tick(30) / 1000
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT or (evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE):
                return
            if evento.type != pygame.KEYDOWN:
                continue
            if evento.key == pygame.K_SPACE:
                pausa = not pausa
                acumulado = 0
            elif evento.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_HOME, pygame.K_END):
                destino = {pygame.K_LEFT: rep.tick - 1, pygame.K_RIGHT: rep.tick + 1,
                           pygame.K_HOME: 0, pygame.K_END: rep.total}[evento.key]
                rep.ir_a(destino)
                pausa, acumulado = True, 0
            elif evento.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                velocidad = min(128, velocidad * 2)
            elif evento.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                velocidad = max(.25, velocidad / 2)
        if not pausa:
            acumulado += segundos * velocidad
            pasos = int(acumulado)
            if pasos:
                rep.ir_a(rep.tick + pasos)
                acumulado -= pasos
            if rep.tick == rep.total:
                pausa = True
        cuadro = dibujar(rep, velocidad, pausa)
        area = cuadro.get_rect().fit(ventana.get_rect())
        ventana.fill(FONDO)
        ventana.blit(pygame.transform.smoothscale(cuadro, area.size), area)
        pygame.display.flip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--guardar-cuadros", type=Path, metavar="CARPETA")
    parser.add_argument("--cada", type=int, default=10, help="intervalo entre PNG (default: 10 ticks)")
    args = parser.parse_args(argv)
    try:
        with args.trace.open(encoding="utf-8") as archivo:
            rep = Reproductor(json.load(archivo))
        if args.guardar_cuadros:
            rutas = guardar_cuadros(rep, args.guardar_cuadros, args.cada)
            print(f"{len(rutas)} cuadros en {args.guardar_cuadros}")
        else:
            reproducir(rep)
        return 0
    except (OSError, ValueError, KeyError, TypeError, pygame.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
