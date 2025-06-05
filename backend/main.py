"""
Haupteinstiegspunkt für das air-Q Backend.

Diese FastAPI-Anwendung sammelt kontinuierlich Daten von air-Q Sensoren
und stellt sie über eine REST-API zur Verfügung.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .api import router as sensor_router
from .task import start_poller, stop_poller
from .db import init_db, close_db
from .config import settings
from .metrics.prometheus_metrics import get_prometheus_metrics, get_content_type

# Logging konfigurieren
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifecycle-Management für die FastAPI-Anwendung.
    
    Verwaltet Startup- und Shutdown-Prozesse für Datenbank und Polling.
    """
    # Startup
    logger.info("🚀 air-Q Backend startet...")
    
    try:
        # Datenbank initialisieren
        logger.info("📊 Initialisiere Datenbank...")
        await init_db()
        
        # Polling-Task starten
        logger.info("🔄 Starte Sensor-Polling...")
        app.state.poller = start_poller()
        
        logger.info("✅ Backend erfolgreich gestartet")
        
        yield  # Anwendung läuft
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Startup: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🛑 Backend wird heruntergefahren...")
        
        # Polling stoppen
        if hasattr(app.state, 'poller'):
            logger.info("⏹️ Stoppe Sensor-Polling...")
            await stop_poller(app.state.poller)
        
        # Datenbankverbindung schließen
        logger.info("🔌 Schließe Datenbankverbindung...")
        await close_db()
        
        logger.info("✅ Backend ordnungsgemäß beendet")


# FastAPI App erstellen
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="""
    Backend-API für air-Q Luftqualitätssensoren.
    
    Diese API sammelt kontinuierlich Daten von air-Q Sensoren, 
    entschlüsselt sie und stellt sie über REST-Endpunkte zur Verfügung.
    
    ## Features
    
    * **Automatisches Polling**: Kontinuierliche Datensammlung von konfigurierten Sensoren
    * **Datenverschlüsselung**: Sichere Entschlüsselung der air-Q Sensordaten  
    * **Flexible API**: Filterung nach Zeitraum, Sensor und Paginierung
    * **Health Monitoring**: Status-Endpunkte für Überwachung
    * **PostgreSQL**: Robuste Datenspeicherung mit Indexierung
    
    ## Konfiguration
    
    Die Anwendung wird über Umgebungsvariablen konfiguriert:
    - `AIRQ_HOST`: IP-Adresse des air-Q Sensors
    - `AIRQ_PASSWORD`: Entschlüsselungspasswort  
    - `AIRQ_SENSORS`: Komma-getrennte Liste der Sensor-Pfade
    - `DATABASE_URL`: PostgreSQL-Verbindungsstring
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Router einbinden
app.include_router(sensor_router)

# Prometheus Metrics Endpoint
@app.get(
    "/metrics",
    tags=["monitoring"],
    summary="Prometheus Metrics",
    description="Liefert Prometheus-Metriken im Text-Format"
)
async def metrics() -> Response:
    """
    Prometheus Metrics Endpoint.
    
    Returns:
        Response: Prometheus-Metriken im Text-Format
    """
    return Response(
        content=get_prometheus_metrics(),
        media_type=get_content_type()
    )

# Root-Endpunkt
@app.get(
    "/",
    tags=["root"],
    summary="API-Informationen",
    description="Gibt grundlegende Informationen über die API zurück."
)
async def read_root() -> dict[str, str]:
    """
    Root-Endpunkt mit API-Informationen.
    
    Returns:
        Grundlegende API-Informationen
    """
    return {
        "message": "air-Q Backend API",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/sensors/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info("🌟 Starte air-Q Backend im Development-Modus")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )