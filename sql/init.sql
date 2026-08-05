-- =========================================================================
-- GRUPO PUERTOMAR - Control de ciclos de esterilizacion
-- Script de inicializacion para Docker (PostgreSQL 18)
-- Ejecutado automaticamente por postgres al crear el volumen por primera vez.
-- =========================================================================

BEGIN;

-- -------------------------------------------------------------------------
-- Tabla: lote
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lote (
    lote_id      VARCHAR(20)  PRIMARY KEY,
    producto     VARCHAR(120) NOT NULL,
    creado_en    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE lote IS 'Lote de produccion que pasa por un ciclo de esterilizacion.';

-- -------------------------------------------------------------------------
-- Tabla: ciclo_esterilizacion
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ciclo_esterilizacion (
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

    CONSTRAINT uq_ciclo_autoclave_inicio  UNIQUE (autoclave, inicio),
    CONSTRAINT chk_ciclo_fin_posterior    CHECK (fin > inicio),
    CONSTRAINT chk_ciclo_temp_rango       CHECK (temperatura_minima <= temperatura_maxima),
    CONSTRAINT chk_ciclo_pres_rango       CHECK (presion_minima <= presion_maxima),
    CONSTRAINT chk_ciclo_temp_positiva    CHECK (temperatura_minima > 0),
    CONSTRAINT chk_ciclo_pres_positiva    CHECK (presion_minima > 0)
);

COMMENT ON TABLE ciclo_esterilizacion IS 'Ciclo de esterilizacion asociado a un lote.';

-- -------------------------------------------------------------------------
-- Tabla: lectura
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lectura (
    lectura_id   BIGSERIAL     PRIMARY KEY,
    ciclo_id     BIGINT        NOT NULL
        REFERENCES ciclo_esterilizacion (ciclo_id) ON DELETE CASCADE,
    fecha_hora   TIMESTAMPTZ   NOT NULL,
    temperatura  NUMERIC(6,2)  NOT NULL,
    presion      NUMERIC(6,2)  NOT NULL,

    CONSTRAINT uq_lectura_ciclo_fecha         UNIQUE (ciclo_id, fecha_hora),
    CONSTRAINT chk_lectura_temp_positiva      CHECK (temperatura > 0),
    CONSTRAINT chk_lectura_pres_positiva      CHECK (presion > 0)
);

COMMENT ON TABLE lectura IS 'Lectura puntual de temperatura/presion durante un ciclo.';

-- -------------------------------------------------------------------------
-- Indices
-- -------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_lectura_ciclo_fecha   ON lectura (ciclo_id, fecha_hora);
CREATE INDEX IF NOT EXISTS idx_ciclo_autoclave_inicio ON ciclo_esterilizacion (autoclave, inicio);
CREATE INDEX IF NOT EXISTS idx_ciclo_lote_id          ON ciclo_esterilizacion (lote_id);

COMMIT;

-- -------------------------------------------------------------------------
-- Vista: v_lectura_clasificada
-- -------------------------------------------------------------------------
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
