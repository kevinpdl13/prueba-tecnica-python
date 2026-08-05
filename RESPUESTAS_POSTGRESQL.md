# Respuestas - Preguntas de PostgreSQL (25 puntos)

> Nota: el SQL completo y ejecutable de las tablas y la consulta del
> punto 5.4 está en `sql/schema.sql`. Aquí se explica el razonamiento
> detrás de cada decisión.

---

## 1. Modelado e integridad (5 puntos)

Las sentencias `CREATE TABLE` completas están en `sql/schema.sql`. El resumen de las decisiones clave:

```sql
CREATE TABLE lote (
    lote_id      VARCHAR(20)  PRIMARY KEY,
    producto     VARCHAR(120) NOT NULL,
    creado_en    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

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
    CONSTRAINT uq_ciclo_autoclave_inicio UNIQUE (autoclave, inicio),
    CONSTRAINT chk_ciclo_fin_posterior_inicio CHECK (fin > inicio),
    CONSTRAINT chk_ciclo_temperatura_rango CHECK (temperatura_minima <= temperatura_maxima),
    CONSTRAINT chk_ciclo_presion_rango CHECK (presion_minima <= presion_maxima)
);

CREATE TABLE lectura (
    lectura_id   BIGSERIAL     PRIMARY KEY,
    ciclo_id     BIGINT        NOT NULL
        REFERENCES ciclo_esterilizacion (ciclo_id) ON DELETE CASCADE,
    fecha_hora   TIMESTAMPTZ   NOT NULL,
    temperatura  NUMERIC(6,2)  NOT NULL,
    presion      NUMERIC(6,2)  NOT NULL,
    CONSTRAINT uq_lectura_ciclo_fecha UNIQUE (ciclo_id, fecha_hora)
);
```

**Por qué así:**

- **`lote` y `ciclo_esterilizacion` en la base de datos el modelo y la relación real del negocio puede ser: un lote *podría* tener más de un ciclo (reproceso). Separar respeta la 3FN y no me obliga a rediseñar el esquema si el negocio cambia.
- **`ON DELETE RESTRICT` de ciclo hacia lote, `ON DELETE CASCADE` de lectura hacia ciclo.** No quiero que se pueda borrar un lote "por accidente" si ya tiene un ciclo registrado (eso protege trazabilidad regulatoria. En cambio, si se elimina un ciclo completo (por ejemplo, se anuló por error de carga), sus lecturas ya no tienen sentido por sí solas, así que cascada es razonable ahí.
- **`CHECK` la base de datos es la última línea de defensa: si mañana otro sistema escribe directo a la tabla (una carga masiva, un ETL), el `CHECK` protege la integridad igual.
- **`UNIQUE (autoclave, inicio)` y `UNIQUE (ciclo_id, fecha_hora)`.** Evitan duplicar la misma lectura o el mismo ciclo si se reprocesa el mismo archivo JSON dos veces (idempotencia).
- **No hay columna para "clasificación" ni "estado del lote".** Son 100% derivables de datos que ya existen (temperatura/presión vs. rangos), así que se calculan con una `VIEW` (`v_lectura_clasificada`) en vez de guardarse. Esto cumple literalmente el punto 5.4: *"evitar almacenar en columnas valores que puedan calcularse fácilmente"*.

Definición SQL de la vista usada:

```sql
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
```

---

## 2. Consulta analítica (5 puntos)

```sql
SELECT
    c.autoclave,
    date_trunc('month', c.inicio) AS mes,
    COUNT(DISTINCT c.ciclo_id) AS lotes_procesados,
    ROUND(AVG(l.temperatura), 2) AS temperatura_promedio,
    COUNT(*) FILTER (WHERE vlc.clasificacion <> 'NORMAL') AS lecturas_fuera_de_rango,
    ROUND(
        100.0 * COUNT(DISTINCT c.ciclo_id) FILTER (
            WHERE NOT EXISTS (
                SELECT 1 FROM v_lectura_clasificada x
                WHERE x.ciclo_id = c.ciclo_id AND x.clasificacion <> 'NORMAL'
            )
        ) / NULLIF(COUNT(DISTINCT c.ciclo_id), 0),
    2) AS porcentaje_lotes_aprobados
FROM ciclo_esterilizacion c
JOIN lectura l ON l.ciclo_id = c.ciclo_id
JOIN v_lectura_clasificada vlc ON vlc.lectura_id = l.lectura_id
GROUP BY c.autoclave, date_trunc('month', c.inicio)
ORDER BY c.autoclave, mes;
```

**Cómo evita la división por cero:** uso `NULLIF(COUNT(...), 0)` como denominador. Si `COUNT(DISTINCT c.ciclo_id)` da 0 (no debería pasar por el `GROUP BY`, pero es buena práctica defensiva), `NULLIF` convierte ese 0 en `NULL`, y en PostgreSQL cualquier división entre `NULL` da `NULL` en vez de lanzar error.

**Por qué `date_trunc('month', c.inicio)`:** `date_trunc` conserva el tipo `timestamp`, lo que permite ordenar cronológicamente.
---

## 3. Índices y plan de ejecución (5 puntos)

Para una consulta que filtra por `autoclave` y `fecha_hora`, y luego ordena por `fecha_hora`, propondría un **índice compuesto**:

```sql
CREATE INDEX idx_ciclo_autoclave_fecha ON ciclo_esterilizacion (autoclave, inicio);
```

**Por qué compuesto y en ese orden:** PostgreSQL usa índices B-Tree de izquierda a derecha. Si el índice es `(autoclave, fecha_hora)`, una consulta que filtra por `autoclave = 'AUT-03' AND fecha_hora BETWEEN ...` puede usar el índice para ambas condiciones Y además obtener las filas ya ordenadas por `fecha_hora` dentro de cada autoclave, evitando un `Sort` adicional al final del plan.

**Cómo verificaría su utilidad:**

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM ciclo_esterilizacion
WHERE autoclave = 'AUT-03' AND inicio BETWEEN '2026-08-01' AND '2026-08-31'
ORDER BY inicio;
```

Revisaría:
- Que el plan muestre `Index Scan` o `Index Only Scan` sobre `idx_ciclo_autoclave_fecha`, y no `Seq Scan`.
- El campo `Buffers: shared hit/read` para saber cuántas páginas realmente se leyeron de disco vs. caché — un índice "útil" en teoría pero con muchos `read` indica que ni siquiera está en memoria.
- Que el `cost` estimado y el tiempo real (`actual time`) sean bajos comparados con un escaneo secuencial de la misma consulta.

**Cuándo PostgreSQL preferiría un escaneo secuencial (`Seq Scan`) aunque exista el índice:** 

1- Cuando la consulta devuelve un gran porcentaje de las filas (baja selectividad):
Si el filtro devuelve una cantidad muy alta de datos (por ejemplo, buscar un autoclave que contiene el 40% o 50% de todas las lecturas de la base de datos), leer la tabla completa de forma continua (Seq Scan) es más rápido para el disco que estar saltando de página en página siguiendo las referencias del índice (Index Scan).

2-Cuando la tabla es muy pequeña:
Si la tabla tiene apenas unas pocas decenas o cientos de filas, todas caben en un solo bloque de memoria. En ese caso, leer la tabla completa de un solo golpe es más rápido que el esfuerzo adicional de abrir y consultar la estructura del índice.

(Nota técnica: El planificador de consultas de PostgreSQL decide esto automáticamente consultando sus estadísticas internas en la tabla pg_stats).
---

## 4. Concurrencia y transacciones (5 puntos)

**Escenario:** dos procesos intentan cerrar simultáneamente el mismo ciclo de esterilización (ej. ambos quieren marcar `fin` o cambiar un estado del ciclo al mismo tiempo).

**Solución propuesta: bloqueo pesimista con `SELECT ... FOR UPDATE` dentro de una transacción explícita.**

```sql
BEGIN;

SELECT ciclo_id, fin
FROM ciclo_esterilizacion
WHERE ciclo_id = 123
FOR UPDATE;  -- bloquea la fila hasta que termine la transacción

-- (aquí la aplicación valida en código que el ciclo no esté ya cerrado)

UPDATE ciclo_esterilizacion
SET fin = now()
WHERE ciclo_id = 123;

COMMIT;
```

**Por qué esta solución y no otra:**

- `FOR UPDATE` toma un bloqueo de fila a nivel de `ROW EXCLUSIVE`. Si el proceso B intenta el mismo `SELECT ... FOR UPDATE` sobre la misma fila mientras el proceso A no ha hecho `COMMIT`, B queda **esperando** hasta que A termine, y entonces ve el dato ya actualizado (evita que ambos lean el mismo estado "abierto" y ambos intenten cerrarlo como si fueran los primeros).

- **Nivel de aislamiento:** con el nivel por defecto de PostgreSQL, `READ COMMITTED`, esto ya es suficiente porque el bloqueo de fila es explícito vía `FOR UPDATE`. No haría falta subir a `SERIALIZABLE` (que añade más overhead y posibles reintentos por errores de serialización) porque el conflicto es sobre una sola fila puntual, no sobre una regla de negocio que dependa de múltiples filas o rangos.

- **¿Por qué Bloqueo Pesimista y no Control de Versiones (Optimista)?:** El cierre de un ciclo de esterilización es una operación crítica que ocurre una sola vez por ciclo. El bloqueo pesimista garantiza que el primer proceso complete el cierre sin que la aplicación tenga que implementar lógica compleja de reintentos por fallos de concurrencia.

---

## 5. Características modernas y operación (5 puntos)

**Particionamiento declarativo por rango para `lectura`:**

Lo utilizaría cuando la tabla de lectura crezca a millones de registros, provocando que las consultas de reportes y las tareas de mantenimiento de la base de datos se vuelvan lentas.

Organizaría las particiones por mes utilizando la columna fecha_hora:

```sql
CREATE TABLE lectura (
    lectura_id   BIGSERIAL,
    ciclo_id     BIGINT NOT NULL,
    fecha_hora   TIMESTAMPTZ NOT NULL,
    temperatura  NUMERIC(6,2) NOT NULL,
    presion      NUMERIC(6,2) NOT NULL,
    PRIMARY KEY (lectura_id, fecha_hora)
) PARTITION BY RANGE (fecha_hora);

CREATE TABLE lectura_2026_08 PARTITION OF lectura
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE TABLE lectura_2026_09 PARTITION OF lectura
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
```

**Por qué por mes y no por autoclave o por año:** las consultas típicas del caso (reportes mensuales, la consulta analítica de la pregunta 2) ya filtran por mes, así que PostgreSQL puede hacer *partition pruning* y tocar solo la partición relevante en vez de la tabla completa. Particionar por año sería demasiado para el volumen de una planta (particiones enormes); por autoclave perdería el beneficio de purgar datos antiguos completos.

**Dos prácticas de mantenimiento/monitoreo relevantes para tablas de alta escritura en PostgreSQL 18:**

1. **Depuración instantánea de datos antiguos (DETACH PARTITION):**
En lugar de ejecutar un DELETE FROM lectura WHERE fecha_hora < ... (que es muy lento, bloquea la base de datos y deja espacio basura), se desacopla la partición del mes antiguo mediante ALTER TABLE ... DETACH PARTITION. Es una operación instantánea que no interrumpe la operación de la planta.
   
2. **Ajuste de actualización de estadísticas (Autovacuum Analyze)** Como la tabla recibe miles de registros continuamente, las estadísticas internas de PostgreSQL se desactualizan rápido. Ajustar el autovacuum para que actualice las estadísticas de esta tabla con mayor frecuencia garantiza que el optimizador de consultas siga eligiendo siempre los mejores índices.
