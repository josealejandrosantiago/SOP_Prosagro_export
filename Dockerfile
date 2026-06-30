# SOP Prosagro Export — imagen de la app Streamlit
# Se construye en GitHub Actions (az acr build) y corre en Azure App Service.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# 1) Dependencias primero (capa cacheable: no se reinstala si solo cambia el código)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 2) Código
COPY . .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
