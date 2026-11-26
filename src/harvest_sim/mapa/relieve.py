"""Relieve: alturas del DEM Copernicus GLO-30 en el centro de cada celda de la cuadrícula.  [Joel]

Especificación: docs/especificacion_terreno.md §8. El DEM (EPSG:4326, ~30 m) se remuestrea con interpolación
bilineal (`rasterio.warp.reproject`) directamente en el marco de la cuadrícula: una transformación afín girada
con el rumbo de los surcos, en UTM. No se reinventa la interpolación.

La copia local del DEM (`config/mapas/el_pueblito_dem.tif`) es solo la ventana de la zona, leída del COG
público. Así el mapa se puede regenerar sin red:

    https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N21_00_W103_00_DEM/
    Copernicus_DSM_COG_10_N21_00_W103_00_DEM.tif
"""

from __future__ import annotations

import math
from pathlib import Path

ATRIBUCION_DEM = (
    "Relieve: Copernicus DEM GLO-30. © DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH 2014-2018, "
    "provisto bajo COPERNICUS por la Unión Europea y la ESA; todos los derechos reservados."
)


def transformacion_cuadricula(geo: dict, tamano_celda_m: float):
    """Afín de (columna, fila) de la cuadrícula a UTM: E = E0 + s·sinθ·col − s·cosθ·fila,
    N = N0 + s·cosθ·col + s·sinθ·fila (el mismo marco de convertir.Marco)."""
    from affine import Affine

    t = math.radians(geo["rumbo_grados"])
    s = tamano_celda_m
    e0, n0 = geo["origen_utm"]
    return Affine(s * math.sin(t), -s * math.cos(t), e0, s * math.cos(t), s * math.sin(t), n0)


def alturas_en_cuadricula(ruta_dem: str | Path, geo: dict, tamano_celda_m: float, ancho: int, alto: int):
    """Matriz alto × ancho (numpy) con la altura bilineal del DEM en el centro de cada celda."""
    import numpy as np
    import rasterio
    from rasterio.warp import Resampling, reproject

    destino = np.full((alto, ancho), np.nan, dtype="float64")
    with rasterio.open(ruta_dem) as fuente:
        reproject(
            source=rasterio.band(fuente, 1),
            destination=destino,
            src_nodata=fuente.nodata,
            dst_transform=transformacion_cuadricula(geo, tamano_celda_m),
            dst_crs=f"EPSG:{geo['epsg']}",
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    return destino


def agregar_alturas(mapa: dict, ruta_dem: str | Path) -> list[str]:
    """Agrega `altura_m` (metros, 2 decimales) al mapa y la atribución del DEM a `geo.atribucion`.
    Devuelve las líneas del reporte. Falla si el DEM no cubre toda la cuadrícula."""
    alturas = alturas_en_cuadricula(ruta_dem, mapa["geo"], mapa["tamano_celda_m"], mapa["ancho"], mapa["alto"])
    import numpy as np

    if not np.isfinite(alturas).all():
        faltan = int((~np.isfinite(alturas)).sum())
        raise ValueError(f"el DEM {Path(ruta_dem).name} no cubre {faltan} celdas de la cuadrícula")
    mapa["altura_m"] = [[round(float(h), 2) for h in fila] for fila in alturas]
    if ATRIBUCION_DEM not in mapa["geo"]["atribucion"]:
        mapa["geo"]["atribucion"] = f"{mapa['geo']['atribucion']} {ATRIBUCION_DEM}"
    s = mapa["tamano_celda_m"]
    campo = {tuple(c) for celdas in mapa["lotes"].values() for c in celdas}
    pendientes = [abs(alturas[y + dy, x + dx] - alturas[y, x]) / s * 100
                  for x, y in campo for dx, dy in ((1, 0), (0, 1)) if (x + dx, y + dy) in campo]
    h_campo = [alturas[y, x] for x, y in campo]
    return [f"relieve: {alturas.min():.1f} a {alturas.max():.1f} m en la cuadrícula; en el campo "
            f"{min(h_campo):.1f} a {max(h_campo):.1f} m, pendiente media {np.mean(pendientes):.1f} %, "
            f"p95 {np.percentile(pendientes, 95):.1f} %, máxima {max(pendientes):.1f} % (DEM {Path(ruta_dem).name}; "
            f"es un modelo de superficie: incluye árboles y construcciones)"]
