FROM python:3.12-slim

# Evitar bloqueos interactivos durante la instalación
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Instalar dependencias del sistema (ffmpeg y nodejs para descargas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Crear el usuario y crear DE ANTEMANO las carpetas con permisos de escritura
RUN useradd -m -u 1000 botuser \
    && mkdir -p /app/data /app/downloads /app/sessions \
    && chown -R botuser:botuser /app

WORKDIR /app

# Instalar librerías de python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copiar el proyecto con permisos para botuser
COPY --chown=botuser:botuser . .

# Permisos totales de lectura/escritura en la carpeta /app
RUN chmod -R 777 /app

# Iniciar con el usuario seguro
USER botuser

CMD ["python", "bot.py"]
