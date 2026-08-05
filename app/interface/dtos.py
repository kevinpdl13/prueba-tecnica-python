"""
Modelos Pydantic (DTOs) para request/response bodies de la API FastAPI.

Se mantienen separados de los modelos de dominio (app.domain.models)
para no mezclar las responsabilidades: los modelos de dominio son la
fuente de verdad del negocio; estos son solo los Data Transfer Objects (DTOs)
en la capa HTTP.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Estructura estándar de response (envelope)
# Todos los endpoints devuelven ApiResponse[T]
# ---------------------------------------------------------------------------

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Envelope estándar para todas las respuestas de la API Puertomar."""

    error: str | None = None
    status_code: int
    data: T | None = None
    message: str

    @classmethod
    def ok(cls, data: Any, message: str = "OK", status_code: int = 200) -> "ApiResponse":
        """Respuesta exitosa."""
        return cls(error=None, status_code=status_code, data=data, message=message)

    @classmethod
    def created(cls, data: Any, message: str = "Created") -> "ApiResponse":
        """Respuesta de creación exitosa (201)."""
        return cls(error=None, status_code=201, data=data, message=message)

    @classmethod
    def fail(cls, error: str, status_code: int, message: str) -> "ApiResponse":
        """Respuesta de error."""
        return cls(error=error, status_code=status_code, data=None, message=message)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------

class LecturaInput(BaseModel):
    fecha_hora: str
    temperatura: float
    presion: float


class LoteInput(BaseModel):
    lote_id: str
    producto: str
    autoclave: str
    inicio: str
    fin: str
    temperatura_minima: float
    temperatura_maxima: float
    presion_minima: float
    presion_maxima: float
    lecturas: list[LecturaInput]


class ProcesarLotesRequest(BaseModel):
    """Request DTO para POST /lotes/procesar."""

    lotes: list[LoteInput]


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------

class ResumenLoteResponse(BaseModel):
    total_lecturas: int
    temperatura_promedio: float | None
    temperatura_minima_registrada: float | None
    temperatura_maxima_registrada: float | None
    presion_promedio: float | None
    presion_minima_registrada: float | None
    presion_maxima_registrada: float | None
    numero_alertas: int
    porcentaje_conformes: float
    estado: str


class AlertaDetalle(BaseModel):
    fecha_hora: str
    temperatura: float
    presion: float
    clasificacion: str


class LoteReporteResponse(BaseModel):
    lote_id: str
    producto: str
    autoclave: str
    inicio: str
    fin: str
    resumen: ResumenLoteResponse
    detalle_alertas: list[AlertaDetalle]


class ProcesarLotesPayload(BaseModel):
    lotes: list[LoteReporteResponse]
    errores: list[str]


class LoteListItem(BaseModel):
    lote_id: str
    producto: str
    autoclave: str
    inicio: datetime
    fin: datetime
    temperatura_minima: float
    temperatura_maxima: float
    presion_minima: float
    presion_maxima: float
    creado_en: datetime

    model_config = {"from_attributes": True}


class LecturaDetalle(BaseModel):
    lectura_id: int
    fecha_hora: datetime
    temperatura: float
    presion: float
    clasificacion: str

    model_config = {"from_attributes": True}


class LoteDetalleResponse(BaseModel):
    lote_id: str
    producto: str
    autoclave: str
    inicio: datetime
    fin: datetime
    temperatura_minima: float
    temperatura_maxima: float
    presion_minima: float
    presion_maxima: float
    creado_en: datetime
    lecturas: list[LecturaDetalle]

    model_config = {"from_attributes": True}


class AlertaResumenItem(BaseModel):
    lote_id: str
    autoclave: str
    cantidad_alertas: int
    mayor_desviacion_temperatura: float


class HealthPayload(BaseModel):
    db: str
    version: str
