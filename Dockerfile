# =========================================================================
# Puertomar API - Dockerfile
# =========================================================================
# Python 3.14 slim
FROM python:3.14-slim

# Evita que Python escriba archivos .pyc y desactiva el buffer de stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos primero solo requirements.txt para aprovechar la caché de Docker
# (si el código cambia pero no las dependencias, no se reinstalan)
COPY requirements.txt .

# Instalamos las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código fuente
COPY . .

# Puerto que expone la API
EXPOSE 8000

# Comando de arranque en modo producción
CMD ["uvicorn", "app_fastapi:app", "--host", "0.0.0.0", "--port", "8000"]
