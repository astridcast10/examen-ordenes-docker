FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero las dependencias: se aprovecha la caché de capas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuario sin privilegios
RUN useradd --create-home --shell /usr/sbin/nologin webuser \
    && chown -R webuser:webuser /app
USER webuser

EXPOSE 8000

# migrate crea las tablas internas de Django (sesiones/mensajes) en SQLite local;
# los datos de negocio viven solo en SQL Server y se consumen vía la API.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000 --noreload"]
