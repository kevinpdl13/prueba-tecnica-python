-- =========================================================================
-- GRUPO PUERTOMAR - Control de ciclos de esterilizacion
-- Script de creacion de esquema para PostgreSQL 18
-- =========================================================================

BEGIN;

-- -------------------------------------------------------------------------
-- Tabla: lote
-- -------------------------------------------------------------------------
CREATE TABLE lote (
    lote_id      VARCHAR(20)  PRIMARY KEY,          -- ej. 'AT-2026-0001', codigo de negocio
    producto     VARCHAR(120) NOT NULL,
    creado_en    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE lote IS 'Lote de produccion (atun/sardina) que pasa por un ciclo de esterilizacion.';

-- -------------------------------------------------------------------------
-- Tabla: ciclo_esterilizacion
-- -------------------------------------------------------------------------
CREATE TABLE ciclo_esterilizacion (
    ciclo_id             BIGSERIAL     PRIMARY KEY,
    lote_id              VARCHAR(20)   NOT NULL
        REFERENCES lote (lote_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    autoclave            VARCHAR(20)   NOT NULL,
    inicio               TIMESTAMPTZ   NOT NULL,
    fin                  TIMESTAMPTZ   NOT NULL,
    temperatura_minima   NUMERIC(6,2)  NOT NULL,
    temperatura_maxima   NUMERIC(6,2)  NOT NULL,
    presion_minima       NUMERIC(6,2)  NOT NULL,
    presion_maxima       NUMERIC(6,2)  NOT NULL,

    -- Un mismo lote no deberia repetir el ciclo exacto; y un autoclave no
    -- puede tener dos ciclos con el mismo inicio (evita duplicados de carga).
    CONSTRAINT uq_ciclo_autoclave_inicio UNIQUE (autoclave, inicio),

    CONSTRAINT chk_ciclo_fin_posterior_inicio CHECK (fin > inicio),
    CONSTRAINT chk_ciclo_temperatura_rango CHECK (temperatura_minima <= temperatura_maxima),
    CONSTRAINT chk_ciclo_presion_rango CHECK (presion_minima <= presion_maxima),
    CONSTRAINT chk_ciclo_temperatura_positiva CHECK (temperatura_minima > 0),
    CONSTRAINT chk_ciclo_presion_positiva CHECK (presion_minima > 0)
);

COMMENT ON TABLE ciclo_esterilizacion IS 'Ciclo de esterilizacion asociado a un lote: ventana de tiempo y rangos permitidos.';

-- -------------------------------------------------------------------------
-- Tabla: lectura
-- -------------------------------------------------------------------------
-- Nota: NO se guarda la columna "clasificacion" (NORMAL / ALERTA_*) porque
-- es 100% derivable de temperatura, presion y los rangos del ciclo. Se
-- calcula en la VIEW v_lectura_clasificada mas abajo.
CREATE TABLE lectura (
    lectura_id   BIGSERIAL     PRIMARY KEY,
    ciclo_id     BIGINT        NOT NULL
        REFERENCES ciclo_esterilizacion (ciclo_id) ON DELETE CASCADE,
    fecha_hora   TIMESTAMPTZ   NOT NULL,
    temperatura  NUMERIC(6,2)  NOT NULL,
    presion      NUMERIC(6,2)  NOT NULL,

    -- Evita cargar dos veces la misma lectura para el mismo ciclo.
    CONSTRAINT uq_lectura_ciclo_fecha UNIQUE (ciclo_id, fecha_hora),
    CONSTRAINT chk_lectura_temperatura_positiva CHECK (temperatura > 0),
    CONSTRAINT chk_lectura_presion_positiva CHECK (presion > 0)
);

COMMENT ON TABLE lectura IS 'Lectura puntual de temperatura/presion durante un ciclo de esterilizacion.';

-- -------------------------------------------------------------------------
-- Indices razonables (punto 5.4: consultas por lote, autoclave y fechas)
-- -------------------------------------------------------------------------

-- Consultas frecuentes: "lecturas de un ciclo especifico ordenadas por fecha".
CREATE INDEX idx_lectura_ciclo_fecha ON lectura (ciclo_id, fecha_hora);

-- Consultas por autoclave y rango de fechas (ej. reportes mensuales, o la
-- pregunta 3 de PostgreSQL sobre filtrar por autoclave + fecha_hora).
CREATE INDEX idx_ciclo_autoclave_inicio ON ciclo_esterilizacion (autoclave, inicio);

-- Consultas por lote (ej. "traer el ciclo de tal lote").
CREATE INDEX idx_ciclo_lote_id ON ciclo_esterilizacion (lote_id);

COMMIT;

-- =========================================================================
-- Vista auxiliar: clasifica cada lectura sin necesidad de guardar la
-- clasificacion como columna (evita redundancia, punto 5.4 del enunciado).
-- =========================================================================
CREATE OR REPLACE VIEW v_lectura_clasificada AS
SELECT
    l.lectura_id,
    l.ciclo_id,
    c.lote_id,
    c.autoclave,
    l.fecha_hora,
    l.temperatura,
    l.presion,
    CASE
        WHEN (l.temperatura < c.temperatura_minima OR l.temperatura > c.temperatura_maxima)
         AND (l.presion     < c.presion_minima     OR l.presion     > c.presion_maxima)
            THEN 'ALERTA_MULTIPLE'
        WHEN (l.temperatura < c.temperatura_minima OR l.temperatura > c.temperatura_maxima)
            THEN 'ALERTA_TEMPERATURA'
        WHEN (l.presion < c.presion_minima OR l.presion > c.presion_maxima)
            THEN 'ALERTA_PRESION'
        ELSE 'NORMAL'
    END AS clasificacion
FROM lectura l
JOIN ciclo_esterilizacion c ON c.ciclo_id = l.ciclo_id;

-- =========================================================================
-- Consulta solicitada (punto 5.4, ultimo bullet):
-- "lotes con alertas, cantidad de alertas y mayor desviacion de temperatura"
-- =========================================================================
-- "Mayor desviacion de temperatura" se interpreta como la mayor diferencia
-- absoluta entre la temperatura leida y el limite de rango mas cercano que
-- violo (si temperatura > maxima, desviacion = temperatura - maxima; si
-- temperatura < minima, desviacion = minima - temperatura).
SELECT
    c.lote_id,
    c.autoclave,
    COUNT(*) FILTER (WHERE vlc.clasificacion <> 'NORMAL')                    AS cantidad_alertas,
    MAX(
        GREATEST(
            vlc.temperatura - c.temperatura_maxima,   -- positivo si excede el maximo
            c.temperatura_minima - vlc.temperatura,   -- positivo si esta bajo el minimo
            0                                          -- 0 si esta dentro de rango
        )
    ) AS mayor_desviacion_temperatura
FROM v_lectura_clasificada vlc
JOIN ciclo_esterilizacion c ON c.ciclo_id = vlc.ciclo_id
GROUP BY c.lote_id, c.autoclave
HAVING COUNT(*) FILTER (WHERE vlc.clasificacion <> 'NORMAL') > 0
ORDER BY cantidad_alertas DESC, mayor_desviacion_temperatura DESC;

-- =========================================================================
-- Datos de ejemplo (opcional, util para probar el script)
-- =========================================================================
-- INSERT INTO lote (lote_id, producto) VALUES ('AT-2026-0001', 'Atun en aceite 170 g');
-- INSERT INTO ciclo_esterilizacion (lote_id, autoclave, inicio, fin, temperatura_minima, temperatura_maxima, presion_minima, presion_maxima)
-- VALUES ('AT-2026-0001', 'AUT-03', '2026-08-01T08:00:00-05:00', '2026-08-01T09:15:00-05:00', 116.0, 123.0, 1.20, 1.80);
-- INSERT INTO lectura (ciclo_id, fecha_hora, temperatura, presion)
-- VALUES (1, '2026-08-01T08:10:00-05:00', 117.2, 1.35),
--        (1, '2026-08-01T08:20:00-05:00', 124.1, 1.62);
