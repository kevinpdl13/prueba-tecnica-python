# Grupo Puertomar — Control de Ciclos de Esterilización

Solución integral a la prueba técnica **"Ingeniero de Desarrollo | Python - Nivel Medio | PostgreSQL"**.

Esta aplicación, Ofrece **dos modalidades de operación 100% funcionales e independientes**, compartiendo el mismo núcleo de reglas de negocio (`LoteProcessor`):

1. **Modo CLI (Consola / Archivos JSON)**: Lee directamente archivos `.json` de entrada que esta ubicada en el proyecto (ej. `data/entrada_ejemplo.json`), procesa los lotes, valida los ciclos de esterilización y genera un reporte de salida en formato `.json` (`data/reporte_salida.json`). Funciona de manera autónoma sin requerir base de datos activa.
2. **Modo API REST (FastAPI + PostgreSQL)**: Servicio web HTTP completo expuesto con FastAPI que recibe lotes vía peticiones JSON (o desde el entorno interactivo **Swagger UI** con datos de prueba pre-cargados), persiste los ciclos y lecturas en una base de datos PostgreSQL 18 y responde bajo un formato estándar de API REST (`ApiResponse`).

---

## 🐳 Inicio Rápido con Docker (Recomendado)

> **Esta es la forma más rápida de levantar el proyecto completo sin instalar Python ni PostgreSQL manualmente.**  
> Solo necesitas tener instalado [Docker Desktop](https://www.docker.com/products/docker-desktop/).

### Paso a Paso

**1. Clonar o descomprimir el proyecto:**

**2. Construir las imágenes y levantar los contenedores:**
```bash
docker compose up --build
```

> Docker realiza estos pasos automáticamente:
> - Construye la imagen de la API con **Python 3.14**.
> - Levanta **PostgreSQL 18** y ejecuta `sql/init.sql` para crear todas las tablas y vistas.
> - Espera a que la base de datos esté lista (healthcheck) antes de arrancar la API.

**3. Verificar que todo esté corriendo:**
```bash
docker compose ps
```
Deberías ver dos contenedores en estado `running`:
| Nombre | Puerto | Estado |
|---|---|---|
| `puertomar_db` | `5432` | running (healthy) |
| `puertomar_api` | `8000` | running |

**4. Abrir Swagger UI para probar los endpoints:**

👉 [http://localhost:8000/docs](http://localhost:8000/docs)

**5. Verificar la salud de la API:**
```bash
curl http://localhost:8000/health
```
Respuesta esperada:
```json
{"error": null, "status_code": 200, "data": {"status": "ok"}, "message": "OK"}
```

**6. Enviar un lote de prueba a la API:**
```bash
curl -X POST http://localhost:8000/lotes/procesar \
  -H "Content-Type: application/json" \
  -d '{
    "lotes": [
      {
        "lote_id": "AT-2026-0001",
        "producto": "Atún en aceite 170 g",
        "autoclave": "AUT-03",
        "inicio": "2026-08-01T08:00:00-05:00",
        "fin": "2026-08-01T09:15:00-05:00",
        "temperatura_minima": 116.0,
        "temperatura_maxima": 123.0,
        "presion_minima": 1.20,
        "presion_maxima": 1.80,
        "lecturas": [
          {"fecha_hora": "2026-08-01T08:10:00-05:00", "temperatura": 117.2, "presion": 1.35},
          {"fecha_hora": "2026-08-01T08:20:00-05:00", "temperatura": 124.1, "presion": 1.62}
        ]
      }
    ]
  }'
```

**7. Probar el Modo CLI (Procesamiento por consola en JSON):**
```bash
docker compose exec api python main.py data/entrada_ejemplo.json
```
> El reporte generado `data/reporte_salida.json` se escribirá dentro del contenedor y se sincronizará automáticamente en la carpeta `data/` de tu máquina.

### Detener los contenedores
```bash
docker compose down
```

### Detener y eliminar los datos de la base de datos
```bash
docker compose down -v
```

---

## 1. Requisitos del Sistema

### Opción A: Con Docker (Recomendado)
- **Docker Desktop** (Incluye Docker Compose y no requiere instalar Python ni PostgreSQL localmente).

### Opción B: Instalación Manual / Desarrollo Local
- **Python 3.14+** (Probado en Python 3.14)
- **PostgreSQL 16+** (Probado en PostgreSQL 18. Requerido únicamente para el modo API REST)
- Dependencias indicadas en `requirements.txt` (`fastapi`, `uvicorn`, `psycopg`, `pytest`)

---

## 2. Instalación Manual (Sin Docker)

Si prefieres ejecutar el proyecto localmente sin usar Docker:

```bash
# 1. Crear e ingresar al entorno virtual (Opcional pero recomendado)
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux / macOS

# 2. Instalar las bibliotecas necesarias
pip install -r requirements.txt
```

### Bibliotecas Utilizadas

- **`fastapi`**: Framework web para la construcción de los endpoints REST.
- **`uvicorn[standard]`**: Servidor web ASGI de alto rendimiento.
- **`psycopg[binary]`**: Driver PostgreSQL (psycopg3) para la gestión del pool de conexiones y consultas SQL.
- **`pytest`**: Framework para la ejecución de la suite de pruebas unitarias automatizadas.

---

## 3. Modo 1: Consola / Archivos JSON (CLI)

En esta modalidad, la aplicación procesa archivos JSON locales de entrada sin depender de PostgreSQL.

### Ejecución

```bash
# Opción A: Desde Docker (Recomendado)
docker compose exec api python main.py data/entrada_ejemplo.json

# Opción B: En entorno local con Python
python main.py data/entrada_ejemplo.json
```

### Opciones de línea de comandos

- `entrada` *(Posicional, Obligatorio)*: Ruta al archivo JSON de entrada con la estructura de lotes y lecturas.

### Flujo en Modo CLI

1. Carga y valida la estructura sintáctica del archivo JSON (`data/entrada_ejemplo.json`).
2. Transforma los datos en objetos de dominio (`Lote`, `Lectura`).
3. Ejecuta `LoteProcessor` para validar las fechas del ciclo, los rangos permitidos de temperatura/presión, clasificar las lecturas (`NORMAL`, `ALERTA_TEMPERATURA`, `ALERTA_PRESION`, `ALERTA_MULTIPLE`) y calcular el estado del lote (`APROBADO`, `OBSERVADO`, `RECHAZADO`).
4. Escribe el resultado final en `data/reporte_salida.json` y registra los eventos en consola mediante el módulo `logging`.

---

## 4. Modo 2: API REST (FastAPI + PostgreSQL)

### Configuración de la Base de Datos

Las credenciales de conexión están configuradas mediante el archivo `.env` en la raíz del proyecto (leído de forma nativa por `app/core/config.py`) de no tener el archivo .env por favor crearlo :

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=basededatos
DB_USER=postgres
DB_PASSWORD=contraseña

API_TITLE=Puertomar API
API_VERSION=1.0.0
```

Antes de iniciar la API REST por primera vez, asegúrese de ejecutar el script de creación de tablas y vistas:

**Opción 1: Desde la terminal (CLI)**
```bash
psql -U postgres -d puertomar -f sql/schema.sql
```
*(En Windows, si `psql` no está en el PATH, use la ruta completa: `"C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d puertomar -f sql/schema.sql`)*.

**Opción 2: Desde una herramienta gráfica (pgAdmin / DBeaver / VS Code PostgreSQL)**
1. Abra su cliente de base de datos preferido (ej. **pgAdmin 4** o **DBeaver**).
2. Conéctese a su servidor PostgreSQL y cree la base de datos `puertomar`.
3. Abra el archivo `sql/schema.sql` en la herramienta Query Tool / Editor SQL y ejecútelo completo (`F5` o botón de ejecutar).

### Iniciar el Servidor API

```bash
uvicorn app_fastapi:app --reload
```

El servidor iniciará en **http://localhost:8000**.

### Documentación Interactiva (Swagger UI)

Acceda a la interfaz interactiva desde su navegador web:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

> **Probar el endpoint `POST /lotes/procesar` desde Swagger UI:**
> 1. Ingrese a [http://localhost:8000/docs](http://localhost:8000/docs).
> 2. Despliegue el endpoint `POST /lotes/procesar` y presione **Try it out**.
> 3. El cuerpo de la petición ya cuenta con los datos de `data/entrada_ejemplo.json` **pre-cargados automáticamente en el editor**.
> 4. Haga clic en **Execute** para procesar y persistir los lotes en PostgreSQL.

### Estructura Estándar de Respuesta (`ApiResponse`)

Todos los endpoints de la API REST responden bajo un sobre (*envelope*) unificado en JSON:

```json
{
  "error": null,
  "status_code": 200,
  "data": { ... },
  "message": "OK"
}
```

En caso de error o datos inválidos (ej. un `lote_id` que ya existe en la base de datos):

```json
{
  "error": "Ya existe en la base de datos el lote: AT-2026-0001",
  "status_code": 400,
  "data": null,
  "message": "Bad Request"
}
```

### Catálogo de Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Verificación de salud de la API y conectividad con PostgreSQL. |
| `POST` | `/lotes/procesar` | Procesa un JSON de lotes, ejecuta reglas de negocio y persiste los registros en PostgreSQL. |
| `GET` | `/lotes` | Lista el encabezado de todos los lotes registrados en PostgreSQL. |
| `GET` | `/lotes/reportes` | Recalcula y devuelve el **reporte completo de todos los lotes** almacenados en la base de datos. |
| `GET` | `/lotes/{lote_id}` | Consulta la información detallada de un lote específico con sus lecturas clasificadas. |
| `GET` | `/lotes/{lote_id}/reporte` | Recalcula el reporte completo (resumen y alertas) para un lote específico. |
| `GET` | `/alertas/resumen` | Ejecuta la consulta analítica SQL sobre la vista `v_lectura_clasificada` (lotes con alertas y mayor desviación de temperatura). |

---

## 5. Pruebas Automatizadas

Para ejecutar la suite de pruebas unitarias con `pytest`:

```bash
python -m pytest tests/ -v
```

Cubre los 6 escenarios requeridos en la especificación técnica:

| Escenario de Prueba | Función | Propósito |
|---------------------|---------|-----------|
| 1. Caso Correcto | `test_caso_correcto` | Valida el flujo exitoso de un lote sin lecturas fuera de rango. |
| 2. Fecha Inválida | `test_fecha_invalida` | Comprueba que se lance `FechaInvalidaError` si la fecha de fin es anterior al inicio. |
| 3. Rango Inválido | `test_rango_invalido` | Comprueba que se lance `RangoInvalidoError` si el mínimo supera al máximo. |
| 4. Lectura Fuera de Ciclo | `test_lectura_fuera_de_ciclo` | Lanza `LecturaFueraDeCicloError` si una lectura no pertenece a la ventana del ciclo. |
| 5. Alerta Múltiple | `test_alerta_multiple` | Evalúa la clasificación `ALERTA_MULTIPLE` cuando temperatura y presión fallan simultáneamente. |
| 6. Cálculo de Estado | `test_calculo_de_estado` | Verifica los estados `APROBADO` (0 alertas), `OBSERVADO` (1-2 alertas) y `RECHAZADO` (3+ alertas). |

---

## 6. Estructura del Proyecto

```
puertomar/
├── app/
│   ├── core/
│   │   └── config.py              ← Lectura centralizada de configuración (.env)
│   ├── domain/                    ← Lógica pura de dominio y reglas
│   │   ├── enums.py               → Enumeraciones (EstadoLote, ClasificacionLectura, etc.)
│   │   ├── models.py              → Entidades Lote, Lectura, ClasificacionLectura, EstadoLote
│   │   └── exceptions.py          → Excepciones personalizadas del dominio
│   ├── application/               ← Casos de uso de la aplicación
│   │   └── lote_processor.py      → Procesador principal de validaciones y métricas
│   ├── infrastructure/            ← Adaptadores de persistencia y datos
│   │   ├── json_repository.py     → Carga y guardado de archivos JSON
│   │   ├── db.py                  → Gestión de conexiones psycopg3 con PostgreSQL
│   │   └── postgres_repository.py → Repositorio CRUD y consultas analíticas SQL
│   └── interface/                 ← Interfaces de entrada/salida
│       ├── cli.py                 → Controlador para la ejecución por consola (CLI)
│       ├── api.py                 → Router de FastAPI con los endpoints REST
│       └── dtos.py                → DTOs y esquemas Pydantic con envelope ApiResponse
├── app_fastapi.py                 ← Servidor principal para FastAPI (uvicorn)
├── main.py                        ← Punto de entrada principal para el CLI
├── requirements.txt               ← Lista de dependencias del proyecto
├── Dockerfile                     ← Imagen Docker de la API (Python 3.14 slim)
├── docker-compose.yml             ← Orquestación: API + PostgreSQL
├── .env                           ← Configuración de ambiente (variables PostgreSQL)
├── .env.example                   ← Plantilla de variables de entorno
├── .gitignore                     ← Archivos ignorados por Git
├── data/
│   ├── entrada_ejemplo.json       → Archivo JSON de entrada con 3 lotes de prueba
│   └── reporte_salida.json        → Resultado en JSON generado por el modo CLI
├── sql/
│   ├── schema.sql                 → Script original de creación de tablas e índices
│   └── init.sql                   → Script Docker: inicializa la BD automáticamente
├── tests/
│   └── test_lote_processor.py     → Pruebas unitarias automatizadas
└── RESPUESTAS_POSTGRESQL.md       → Respuestas detalladas a las 5 preguntas sobre PostgreSQL
```

---

## 7. Respuestas Teóricas PostgreSQL

El archivo `RESPUESTAS_POSTGRESQL.md` contiene la solución justificada a las 5 preguntas del caso de estudio:
1. **Modelado e Integridad**: Sentencias `CREATE TABLE` con claves foráneas, restricciones `CHECK`, `UNIQUE` y vista `v_lectura_clasificada`.
2. **Consulta Analítica**: Consulta SQL con `date_trunc`, agregado filtrado y prevención de división por cero con `NULLIF`.
3. **Índices y Plan de Ejecución**: Propuesta de índice compuesto B-Tree `(autoclave, inicio)` y análisis con `EXPLAIN (ANALYZE, BUFFERS)`.
4. **Concurrencia y Transacciones**: Estrategia de bloqueo pesimista mediante `SELECT ... FOR UPDATE`.
5. **Particionamiento y Operación**: Particionamiento declarativo por rango en la tabla `lectura` e instrumentos de mantenimiento en PostgreSQL 18.
