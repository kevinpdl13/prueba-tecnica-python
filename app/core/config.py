"""Configuración centralizada de la aplicación."""

from __future__ import annotations

import os
from dotenv import load_dotenv


# Carga automática de variables del archivo .env a os.environ
load_dotenv()



class Settings:
    """Parámetros de configuración del sistema y base de datos."""

    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "puertomar")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "")

    api_title: str = os.getenv("API_TITLE", "Puertomar API")
    api_version: str = os.getenv("API_VERSION", "1.0.0")
    api_description: str = (
        "API REST para el control de ciclos de esterilización — Grupo Puertomar. "
        "Permite procesar lotes desde JSON, persistirlos en PostgreSQL y consultar reportes analíticos."
    )

    @property
    def dsn(self) -> str:
        """Cadena de conexión PostgreSQL para psycopg3."""
        return (
            f"host={self.db_host} port={self.db_port} "
            f"dbname={self.db_name} user={self.db_user} "
            f"password={self.db_password}"
        )


settings = Settings()
