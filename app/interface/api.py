"""
Router FastAPI con todos los endpoints de la API Puertomar.

Todos los endpoints devuelven la estructura estándar:
{
    "error": null,
    "status_code": 200,
    "data": { ... },
    "message": "OK"
}

Endpoints:
  POST /lotes/procesar          → procesa JSON, guarda en BD, devuelve reporte
  GET  /lotes                   → lista todos los lotes desde BD
  GET  /lotes/{lote_id}         → detalle de un lote con lecturas
  GET  /lotes/{lote_id}/reporte → recalcula reporte completo desde BD
  GET  /alertas/resumen         → consulta analítica (schema.sql)
  GET  /health                  → health check de API y BD
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from psycopg import Connection

from app.application.lote_processor import LoteProcessor
from app.core.config import settings
from app.domain.exceptions import ValidationError
from app.domain.models import Lectura, Lote
from app.infrastructure.db import check_db_connection, get_connection_dep
from app.infrastructure.json_repository import cargar_lotes_desde_dict
from app.infrastructure.postgres_repository import (
    guardar_lotes,
    listar_lotes,
    obtener_lote,
    obtener_resumen_alertas,
    obtener_todos_los_lotes_completos,
)
from app.interface.dtos import (
    AlertaResumenItem,
    ApiResponse,
    HealthPayload,
    LoteDetalleResponse,
    LoteListItem,
    LoteReporteResponse,
    ProcesarLotesPayload,
    ProcesarLotesRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()
_procesador = LoteProcessor()


def _api_error(status_code: int, error_detail: str) -> JSONResponse:
    """
    Construye una JSONResponse de error con el envelope estándar.
    Se usa en lugar de HTTPException para mantener la estructura uniforme.
    """
    http_messages = {
        400: "Bad Request",
        404: "Not Found",
        422: "Unprocessable Entity",
        500: "Internal Server Error",
    }
    body = ApiResponse.fail(
        error=error_detail,
        status_code=status_code,
        message=http_messages.get(status_code, "Error"),
    ).model_dump()
    return JSONResponse(status_code=status_code, content=body)


# ---------------------------------------------------------------------------
# POST /lotes/procesar
# ---------------------------------------------------------------------------

@router.post(
    "/lotes/procesar",
    response_model=ApiResponse[ProcesarLotesPayload],
    status_code=200,
    summary="Procesar lotes y persistir en BD",
    description=(
        "Recibe el JSON de lotes"
        "procesa cada lote con las reglas de negocio, guarda los resultados "
        "en PostgreSQL y devuelve el reporte completo envuelto en la respuesta estándar."
    ),
    responses={
        422: {"description": "Error de validación en los datos de entrada"},
        500: {"description": "Error interno del servidor"},
    },
    tags=["Lotes"],
)
def procesar_lotes(
    body: ProcesarLotesRequest,
    conn: Connection = Depends(get_connection_dep),
) -> Any:
    datos_raw = body.model_dump()

    try:
        lotes = cargar_lotes_desde_dict(datos_raw)
    except ValidationError as exc:
        return _api_error(422, str(exc))
    except Exception as exc:
        logger.error("Error al leer datos de entrada: %s", exc)
        return _api_error(400, f"Error en formato de datos de entrada: {exc}")

    # Validar integridad de dominio de cada lote antes de tocar la base de datos
    for lote in lotes:
        try:
            _procesador.validar_lote(lote)
        except ValidationError as exc:
            logger.warning("Error de validación en lote %s: %s", lote.lote_id, exc)
            return _api_error(422, str(exc))

    reporte = _procesador.procesar_lotes(lotes)

    try:
        guardados = guardar_lotes(lotes, conn)
    except ValueError as exc:
        logger.warning("Intento de insertar lotes duplicados: %s", exc)
        return _api_error(400, str(exc))
    except Exception as exc:
        logger.error("Error de base de datos al guardar lotes: %s", exc)
        return _api_error(500, f"Error en base de datos: {exc}")

    logger.info(
        "POST /lotes/procesar — %d lote(s) procesados y %d guardado(s) en BD.",
        len(lotes),
        guardados,
    )

    # Si hubo errores de lotes reportados por el procesador, se notifica en message
    mensaje = "OK"
    if reporte.get("errores"):
        mensaje = f"Procesado con {len(reporte['errores'])} error(es) en lotes"

    payload = ProcesarLotesPayload(
        lotes=[LoteReporteResponse(**l) for l in reporte["lotes"]],
        errores=reporte["errores"],
    )
    return ApiResponse.ok(data=payload, message=mensaje)


# ---------------------------------------------------------------------------
# GET /lotes
# ---------------------------------------------------------------------------

@router.get(
    "/lotes",
    response_model=ApiResponse[list[LoteListItem]],
    status_code=200,
    summary="Listar todos los lotes",
    description="Devuelve todos los lotes almacenados en PostgreSQL con la información de su ciclo.",
    responses={
        500: {"description": "Error interno del servidor"},
    },
    tags=["Lotes"],
)
def get_lotes(conn: Connection = Depends(get_connection_dep)) -> Any:
    lotes_raw = listar_lotes(conn)
    lotes = [LoteListItem(**row) for row in lotes_raw]
    return ApiResponse.ok(data=lotes, message="OK")


# ---------------------------------------------------------------------------
# GET /lotes/reportes
# ---------------------------------------------------------------------------

@router.get(
    "/lotes/reportes",
    response_model=ApiResponse[list[LoteReporteResponse]],
    status_code=200,
    summary="Reporte completo de todos los lotes",
    description=(
        "Recupera todos los lotes guardados en PostgreSQL con sus lecturas y calcula "
        "el reporte completo (resumen estadístico + detalle de alertas) de cada uno."
    ),
    responses={
        500: {"description": "Error interno del servidor"},
    },
    tags=["Lotes"],
)
def get_reportes_todos_los_lotes(conn: Connection = Depends(get_connection_dep)) -> Any:
    lotes_data = obtener_todos_los_lotes_completos(conn)
    if not lotes_data:
        return ApiResponse.ok(data=[], message="OK")

    lotes_dominio: list[Lote] = []
    for lote_data in lotes_data:
        lecturas = [
            Lectura(
                fecha_hora=row["fecha_hora"] if isinstance(row["fecha_hora"], datetime)
                           else datetime.fromisoformat(str(row["fecha_hora"])),
                temperatura=float(row["temperatura"]),
                presion=float(row["presion"]),
            )
            for row in lote_data["lecturas"]
        ]
        lote_dominio = Lote(
            lote_id=lote_data["lote_id"],
            producto=lote_data["producto"],
            autoclave=lote_data["autoclave"],
            inicio=lote_data["inicio"] if isinstance(lote_data["inicio"], datetime)
                   else datetime.fromisoformat(str(lote_data["inicio"])),
            fin=lote_data["fin"] if isinstance(lote_data["fin"], datetime)
                else datetime.fromisoformat(str(lote_data["fin"])),
            temperatura_minima=float(lote_data["temperatura_minima"]),
            temperatura_maxima=float(lote_data["temperatura_maxima"]),
            presion_minima=float(lote_data["presion_minima"]),
            presion_maxima=float(lote_data["presion_maxima"]),
            lecturas=lecturas,
        )
        lotes_dominio.append(lote_dominio)

    reporte_general = _procesador.procesar_lotes(lotes_dominio)
    reportes = [LoteReporteResponse(**r) for r in reporte_general["lotes"]]
    return ApiResponse.ok(data=reportes, message="OK")


# ---------------------------------------------------------------------------
# GET /lotes/{lote_id}
# ---------------------------------------------------------------------------

@router.get(
    "/lotes/{lote_id}",
    response_model=ApiResponse[LoteDetalleResponse],
    status_code=200,
    summary="Detalle de un lote",
    description=(
        "Devuelve un lote específico desde PostgreSQL con todas sus lecturas "
        "y la clasificación calculada por la vista `v_lectura_clasificada`."
    ),
    responses={
        404: {"description": "Lote no encontrado"},
        500: {"description": "Error interno del servidor"},
    },
    tags=["Lotes"],
)
def get_lote(lote_id: str, conn: Connection = Depends(get_connection_dep)) -> Any:
    lote_data = obtener_lote(lote_id, conn)
    if lote_data is None:
        return _api_error(404, f"Lote '{lote_id}' no encontrado en la base de datos.")
    lote = LoteDetalleResponse(**lote_data)
    return ApiResponse.ok(data=lote, message="OK")


# ---------------------------------------------------------------------------
# GET /lotes/{lote_id}/reporte
# ---------------------------------------------------------------------------

@router.get(
    "/lotes/{lote_id}/reporte",
    response_model=ApiResponse[LoteReporteResponse],
    status_code=200,
    summary="Reporte completo de un lote",
    description=(
        "Recupera un lote desde PostgreSQL y recalcula el reporte completo "
        "(resumen estadístico + detalle de alertas) usando LoteProcessor."
    ),
    responses={
        404: {"description": "Lote no encontrado"},
        422: {"description": "Error de validación en los datos del lote"},
        500: {"description": "Error interno del servidor"},
    },
    tags=["Lotes"],
)
def get_reporte_lote(lote_id: str, conn: Connection = Depends(get_connection_dep)) -> Any:
    lote_data = obtener_lote(lote_id, conn)
    if lote_data is None:
        return _api_error(404, f"Lote '{lote_id}' no encontrado en la base de datos.")

    # Reconstruir objeto de dominio desde los datos de BD
    lecturas = [
        Lectura(
            fecha_hora=row["fecha_hora"] if isinstance(row["fecha_hora"], datetime)
                       else datetime.fromisoformat(str(row["fecha_hora"])),
            temperatura=float(row["temperatura"]),
            presion=float(row["presion"]),
        )
        for row in lote_data["lecturas"]
    ]

    lote_dominio = Lote(
        lote_id=lote_data["lote_id"],
        producto=lote_data["producto"],
        autoclave=lote_data["autoclave"],
        inicio=lote_data["inicio"] if isinstance(lote_data["inicio"], datetime)
               else datetime.fromisoformat(str(lote_data["inicio"])),
        fin=lote_data["fin"] if isinstance(lote_data["fin"], datetime)
            else datetime.fromisoformat(str(lote_data["fin"])),
        temperatura_minima=float(lote_data["temperatura_minima"]),
        temperatura_maxima=float(lote_data["temperatura_maxima"]),
        presion_minima=float(lote_data["presion_minima"]),
        presion_maxima=float(lote_data["presion_maxima"]),
        lecturas=lecturas,
    )

    try:
        reporte = _procesador.procesar_lote(lote_dominio)
    except ValidationError as exc:
        return _api_error(422, str(exc))

    payload = LoteReporteResponse(**reporte)
    return ApiResponse.ok(data=payload, message="OK")


# ---------------------------------------------------------------------------
# GET /alertas/resumen
# ---------------------------------------------------------------------------

@router.get(
    "/alertas/resumen",
    response_model=ApiResponse[list[AlertaResumenItem]],
    status_code=200,
    summary="Resumen analítico de alertas",
    description=(
        "Ejecuta la consulta analítica definida en `sql/schema.sql`: "
        "lotes que tuvieron alertas, cantidad de alertas y mayor desviación "
        "de temperatura registrada."
    ),
    responses={
        500: {"description": "Error interno del servidor"},
    },
    tags=["Alertas"],
)
def get_resumen_alertas(conn: Connection = Depends(get_connection_dep)) -> Any:
    resumen_raw = obtener_resumen_alertas(conn)
    alertas = [AlertaResumenItem(**row) for row in resumen_raw]
    return ApiResponse.ok(data=alertas, message="OK")


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    response_model=ApiResponse[HealthPayload],
    status_code=200,
    summary="Health check",
    description="Verifica que la API esté activa y que la conexión a PostgreSQL funcione.",
    tags=["Sistema"],
)
def health_check() -> Any:
    db_ok = check_db_connection()
    payload = HealthPayload(
        db="connected" if db_ok else "error",
        version=settings.api_version,
    )
    return ApiResponse.ok(data=payload, message="OK")
