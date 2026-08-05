"""
Gestión de conexiones a PostgreSQL usando psycopg3.

Expone `get_connection()` como context manager para ser usado
en repositorios y como dependencia de FastAPI (Depends).

Nota: se usa psycopg.connect() directamente (sin pool externo) para
maximizar la compatibilidad. psycopg_pool es un paquete opcional
separado que no se instala con psycopg[binary].
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg import Connection

from app.core.config import settings

logger = logging.getLogger(__name__)

# DSN validado al arrancar — se guarda para reutilizar en cada conexión.
_dsn: str | None = None


def init_pool() -> None:
    """
    'Inicializa' la capa de acceso a BD.
    Valida la conexión al arrancar FastAPI para detectar errores pronto.
    """
    global _dsn
    logger.info(
        "Conectando a PostgreSQL en %s:%s/%s",
        settings.db_host, settings.db_port, settings.db_name,
    )
    # Prueba la conexión al arrancar para fallar rápido si hay un error de config.
    try:
        with psycopg.connect(settings.dsn) as test_conn:
            test_conn.execute("SELECT 1")
        _dsn = settings.dsn
        logger.info("Conexión a PostgreSQL verificada correctamente.")
    except Exception as exc:
        logger.error("No se pudo conectar a PostgreSQL: %s", exc)
        raise


def close_pool() -> None:
    """Limpieza al apagar la app (no-op con conexiones directas)."""
    global _dsn
    _dsn = None
    logger.info("Capa de conexión a PostgreSQL cerrada.")


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    """
    Context manager que abre una conexión psycopg3, la entrega y la cierra al salir.

    Uso:
        with get_connection() as conn:
            conn.execute(...)
    """
    if _dsn is None:
        raise RuntimeError(
            "La conexión a PostgreSQL no está inicializada. "
            "Asegúrate de que la aplicación FastAPI haya arrancado correctamente."
        )
    with psycopg.connect(_dsn, autocommit=True) as conn:
        yield conn


def get_connection_dep():
    """
    Generador para usar como Depends() en FastAPI.
    Abre una conexión por request y la cierra al terminar.
    """
    with get_connection() as conn:
        yield conn


def check_db_connection() -> bool:
    """Verifica que la conexión a la BD funcione. Usado en /health."""
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as exc:
        logger.error("Fallo en la verificación de conexión a BD: %s", exc)
        return False
