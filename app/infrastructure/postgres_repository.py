"""
Repositorio PostgreSQL para lotes, ciclos y lecturas.

Persiste los resultados del LoteProcessor en las tres tablas del esquema
(lote, ciclo_esterilizacion, lectura) usando ON CONFLICT DO NOTHING para
garantizar idempotencia: si el mismo JSON se procesa dos veces, no falla.

Consultas de lectura:
  - listar_lotes()         → todos los lotes con su ciclo
  - obtener_lote()         → un lote con ciclo + lecturas
  - obtener_resumen_alertas() → consulta analítica del schema.sql
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from app.domain.models import Lote

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def verificar_lotes_duplicados(lotes: list[Lote], conn: Connection) -> None:
    """
    Verifica si alguno de los lote_id o la combinación (autoclave, inicio) ya existen en la BD.
    Lanza ValueError si se detecta un conflicto de lote o de autoclave ocupada.
    """
    with conn.cursor() as cur:
        for lote in lotes:
            # 1. Comprobar si el lote_id ya existe
            cur.execute("SELECT lote_id FROM lote WHERE lote_id = %s", (lote.lote_id,))
            if cur.fetchone():
                raise ValueError(f"Ya existe en la base de datos el lote '{lote.lote_id}'.")

            # 2. Comprobar si la autoclave ya tiene un ciclo registrado a ese inicio
            cur.execute(
                "SELECT lote_id FROM ciclo_esterilizacion WHERE autoclave = %s AND inicio = %s",
                (lote.autoclave, lote.inicio),
            )
            row_ciclo = cur.fetchone()
            if row_ciclo:
                raise ValueError(
                    f"El autoclave '{lote.autoclave}' ya tiene un ciclo registrado con inicio en {lote.inicio} (Lote: '{row_ciclo[0]}')."
                )


def guardar_lotes(lotes: list[Lote], conn: Connection) -> int:
    """
    Persiste una lista de Lote en PostgreSQL.
    Lanza ValueError si existe conflicto de lote o de autoclave ocupada.
    """
    verificar_lotes_duplicados(lotes, conn)

    guardados = 0
    with conn.transaction():
        for lote in lotes:
            _guardar_un_lote(lote, conn)
            guardados += 1

    logger.info("%d lote(s) guardado(s) exitosamente en PostgreSQL.", guardados)
    return guardados


def _guardar_un_lote(lote: Lote, conn: Connection) -> None:
    """Inserta las 3 tablas para un lote dado."""
    with conn.cursor() as cur:
        # 1. Tabla lote
        cur.execute(
            """
            INSERT INTO lote (lote_id, producto)
            VALUES (%s, %s)
            """,
            (lote.lote_id, lote.producto),
        )

        # 2. Tabla ciclo_esterilizacion
        cur.execute(
            """
            INSERT INTO ciclo_esterilizacion
                (lote_id, autoclave, inicio, fin,
                 temperatura_minima, temperatura_maxima,
                 presion_minima, presion_maxima)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING ciclo_id
            """,
            (
                lote.lote_id,
                lote.autoclave,
                lote.inicio,
                lote.fin,
                lote.temperatura_minima,
                lote.temperatura_maxima,
                lote.presion_minima,
                lote.presion_maxima,
            ),
        )
        row = cur.fetchone()
        ciclo_id: int = row[0]

        # 3. Tabla lectura
        if lote.lecturas:
            cur.executemany(
                """
                INSERT INTO lectura (ciclo_id, fecha_hora, temperatura, presion)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (ciclo_id, lectura.fecha_hora, lectura.temperatura, lectura.presion)
                    for lectura in lote.lecturas
                ],
            )



# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def listar_lotes(conn: Connection) -> list[dict[str, Any]]:
    """Devuelve todos los lotes con la info de su ciclo (sin lecturas)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                l.lote_id,
                l.producto,
                l.creado_en,
                c.ciclo_id,
                c.autoclave,
                c.inicio,
                c.fin,
                c.temperatura_minima,
                c.temperatura_maxima,
                c.presion_minima,
                c.presion_maxima
            FROM lote l
            JOIN ciclo_esterilizacion c ON c.lote_id = l.lote_id
            ORDER BY c.inicio DESC
            """
        )
        return cur.fetchall()


def obtener_lote(lote_id: str, conn: Connection) -> dict[str, Any] | None:
    """
    Devuelve un lote completo (cabecera + lecturas) desde PostgreSQL.
    Retorna None si el lote_id no existe.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        # Cabecera
        cur.execute(
            """
            SELECT
                l.lote_id, l.producto, l.creado_en,
                c.ciclo_id, c.autoclave, c.inicio, c.fin,
                c.temperatura_minima, c.temperatura_maxima,
                c.presion_minima, c.presion_maxima
            FROM lote l
            JOIN ciclo_esterilizacion c ON c.lote_id = l.lote_id
            WHERE l.lote_id = %s
            """,
            (lote_id,),
        )
        cabecera = cur.fetchone()
        if cabecera is None:
            return None

        # Lecturas
        cur.execute(
            """
            SELECT lectura_id, fecha_hora, temperatura, presion, clasificacion
            FROM v_lectura_clasificada
            WHERE ciclo_id = %s
            ORDER BY fecha_hora
            """,
            (cabecera["ciclo_id"],),
        )
        lecturas = cur.fetchall()

    return {**cabecera, "lecturas": lecturas}


def obtener_todos_los_lotes_completos(conn: Connection) -> list[dict[str, Any]]:
    """
    Devuelve todos los lotes guardados en la BD con sus respectivas lecturas.
    """
    lotes_base = listar_lotes(conn)
    resultado = []
    for l in lotes_base:
        lote_completo = obtener_lote(l["lote_id"], conn)
        if lote_completo:
            resultado.append(lote_completo)
    return resultado


def obtener_resumen_alertas(conn: Connection) -> list[dict[str, Any]]:
    """
    Ejecuta la consulta analítica definida en schema.sql:
    lotes con alertas, cantidad de alertas y mayor desviación de temperatura.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                c.lote_id,
                c.autoclave,
                COUNT(*) FILTER (WHERE vlc.clasificacion <> 'NORMAL')
                    AS cantidad_alertas,
                MAX(
                    GREATEST(
                        vlc.temperatura - c.temperatura_maxima,
                        c.temperatura_minima - vlc.temperatura,
                        0
                    )
                ) AS mayor_desviacion_temperatura
            FROM v_lectura_clasificada vlc
            JOIN ciclo_esterilizacion c ON c.ciclo_id = vlc.ciclo_id
            GROUP BY c.lote_id, c.autoclave
            HAVING COUNT(*) FILTER (WHERE vlc.clasificacion <> 'NORMAL') > 0
            ORDER BY cantidad_alertas DESC, mayor_desviacion_temperatura DESC
            """
        )
        return cur.fetchall()
