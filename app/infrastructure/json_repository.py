from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.exceptions import (
    ArchivoEntradaError,
    CampoObligatorioError,
)
from app.domain.models import Lectura, Lote

logger = logging.getLogger(__name__)

# Campos obligatorios a nivel de lote. No se incluye "lecturas" aquí
# porque una lista vacía es un caso de negocio válido (lote sin
# lecturas registradas aún), se valida por separado si aplica.
_CAMPOS_OBLIGATORIOS_LOTE = (
    "lote_id",
    "producto",
    "autoclave",
    "inicio",
    "fin",
    "temperatura_minima",
    "temperatura_maxima",
    "presion_minima",
    "presion_maxima",
)


def _parsear_fecha(valor: str, contexto: str) -> datetime:
    try:
        return datetime.fromisoformat(valor)
    except (TypeError, ValueError) as exc:
        raise CampoObligatorioError("fecha_hora/inicio/fin", contexto) from exc


def _validar_campo_no_vacio(datos: dict[str, Any], campo: str, contexto: str) -> Any:
    """Valida que `campo` exista en `datos` y no sea None/"" antes de usarlo."""
    valor = datos.get(campo)
    if valor is None or valor == "":
        raise CampoObligatorioError(campo, contexto)
    return valor


def cargar_lotes_desde_json(ruta_archivo: str | Path) -> list[Lote]:
    ruta = Path(ruta_archivo)
    logger.info("Cargando archivo de entrada: %s", ruta)

    if not ruta.exists():
        raise ArchivoEntradaError(f"El archivo '{ruta}' no existe")

    try:
        contenido = ruta.read_text(encoding="utf-8")
        datos_raw = json.loads(contenido)
    except json.JSONDecodeError as exc:
        raise ArchivoEntradaError(f"El archivo '{ruta}' no es un JSON válido: {exc}") from exc

    if not isinstance(datos_raw, dict) or "lotes" not in datos_raw:
        raise ArchivoEntradaError("El JSON debe contener la clave raíz 'lotes'")

    lotes: list[Lote] = []
    for indice, lote_raw in enumerate(datos_raw["lotes"]):
        contexto = f"lote en posición {indice}"

        for campo in _CAMPOS_OBLIGATORIOS_LOTE:
            _validar_campo_no_vacio(lote_raw, campo, contexto)

        lote_id = lote_raw["lote_id"]
        inicio = _parsear_fecha(lote_raw["inicio"], f"lote {lote_id}, campo inicio")
        fin = _parsear_fecha(lote_raw["fin"], f"lote {lote_id}, campo fin")

        lecturas: list[Lectura] = []
        for i, lectura_raw in enumerate(lote_raw.get("lecturas", [])):
            _validar_campo_no_vacio(lectura_raw, "fecha_hora", f"lote {lote_id}, lectura {i}")
            _validar_campo_no_vacio(lectura_raw, "temperatura", f"lote {lote_id}, lectura {i}")
            _validar_campo_no_vacio(lectura_raw, "presion", f"lote {lote_id}, lectura {i}")
            lecturas.append(
                Lectura(
                    fecha_hora=_parsear_fecha(
                        lectura_raw["fecha_hora"], f"lote {lote_id}, lectura {i}"
                    ),
                    temperatura=float(lectura_raw["temperatura"]),
                    presion=float(lectura_raw["presion"]),
                )
            )

        lotes.append(
            Lote(
                lote_id=lote_id,
                producto=lote_raw["producto"],
                autoclave=lote_raw["autoclave"],
                inicio=inicio,
                fin=fin,
                temperatura_minima=float(lote_raw["temperatura_minima"]),
                temperatura_maxima=float(lote_raw["temperatura_maxima"]),
                presion_minima=float(lote_raw["presion_minima"]),
                presion_maxima=float(lote_raw["presion_maxima"]),
                lecturas=lecturas,
            )
        )

    logger.info("Se cargaron %d lote(s) desde %s", len(lotes), ruta)
    return lotes


def cargar_lotes_desde_dict(datos_raw: dict[str, Any]) -> list[Lote]:
    """
    Parsea y valida la misma estructura que cargar_lotes_desde_json() pero
    aceptando un dict en vez de una ruta de archivo.

    Útil para la API FastAPI: el body JSON del request se parsea con Pydantic
    y luego se pasa directamente aquí para construir los objetos de dominio.
    """
    from app.domain.exceptions import ArchivoEntradaError  # evita import circular en top

    if not isinstance(datos_raw, dict) or "lotes" not in datos_raw:
        raise ArchivoEntradaError("El JSON debe contener la clave raíz 'lotes'")

    lotes: list[Lote] = []
    for indice, lote_raw in enumerate(datos_raw["lotes"]):
        contexto = f"lote en posición {indice}"

        for campo in _CAMPOS_OBLIGATORIOS_LOTE:
            _validar_campo_no_vacio(lote_raw, campo, contexto)

        lote_id = lote_raw["lote_id"]
        inicio = _parsear_fecha(lote_raw["inicio"], f"lote {lote_id}, campo inicio")
        fin = _parsear_fecha(lote_raw["fin"], f"lote {lote_id}, campo fin")

        lecturas: list[Lectura] = []
        for i, lectura_raw in enumerate(lote_raw.get("lecturas", [])):
            _validar_campo_no_vacio(lectura_raw, "fecha_hora", f"lote {lote_id}, lectura {i}")
            _validar_campo_no_vacio(lectura_raw, "temperatura", f"lote {lote_id}, lectura {i}")
            _validar_campo_no_vacio(lectura_raw, "presion", f"lote {lote_id}, lectura {i}")
            lecturas.append(
                Lectura(
                    fecha_hora=_parsear_fecha(
                        lectura_raw["fecha_hora"], f"lote {lote_id}, lectura {i}"
                    ),
                    temperatura=float(lectura_raw["temperatura"]),
                    presion=float(lectura_raw["presion"]),
                )
            )

        lotes.append(
            Lote(
                lote_id=lote_id,
                producto=lote_raw["producto"],
                autoclave=lote_raw["autoclave"],
                inicio=inicio,
                fin=fin,
                temperatura_minima=float(lote_raw["temperatura_minima"]),
                temperatura_maxima=float(lote_raw["temperatura_maxima"]),
                presion_minima=float(lote_raw["presion_minima"]),
                presion_maxima=float(lote_raw["presion_maxima"]),
                lecturas=lecturas,
            )
        )

    logger.info("Se cargaron %d lote(s) desde dict/body.", len(lotes))
    return lotes


def guardar_reporte_json(reporte: dict[str, Any], ruta_salida: str | Path) -> None:
    ruta = Path(ruta_salida)
    ruta.write_text(
        json.dumps(reporte, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info("Reporte de salida escrito en: %s", ruta)
