"""
Punto de entrada FastAPI para la API Puertomar.

Para arrancar el servidor de desarrollo:
    uvicorn app_fastapi:app --reload

Para producción:
    uvicorn app_fastapi:app --host 0.0.0.0 --port 8000 --workers 4

Documentación interactiva disponible en:
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.infrastructure.db import close_pool, init_pool
from app.interface.api import router
from app.interface.dtos import ApiResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("puertomar.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación:
    - Al arrancar: inicializa el pool de conexiones a PostgreSQL.
    - Al apagar: cierra el pool limpiamente.
    """
    logger.info("Arrancando Puertomar API v%s...", settings.api_version)
    init_pool()
    yield
    logger.info("Apagando Puertomar API...")
    close_pool()

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    detalles = [f"{err.get('loc', [])}: {err.get('msg', '')}" for err in exc.errors()]
    mensaje_error = " | ".join(detalles) if detalles else str(exc)
    body = ApiResponse.fail(
        error=mensaje_error,
        status_code=422,
        message="Unprocessable Entity",
    ).model_dump()
    return JSONResponse(status_code=422, content=body)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.exception("Excepción no controlada: %s", exc)
    body = ApiResponse.fail(
        error=str(exc),
        status_code=500,
        message="Internal Server Error",
    ).model_dump()
    return JSONResponse(status_code=500, content=body)


app.include_router(router, prefix="")

logger.info("Puertomar API configurada. Endpoints registrados.")
