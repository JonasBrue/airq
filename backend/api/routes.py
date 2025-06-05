"""
FastAPI Router für air-Q Sensor-Endpunkte.

Dieses Modul definiert alle API-Endpunkte für den Zugriff auf
Sensordaten mit umfassendem Error-Handling und Logging.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from ..db.database import get_session
from ..db.models import SensorData
from ..metrics.prometheus_metrics import get_prometheus_metrics, get_content_type
from .schemas import (
    SensorDataSchema, 
    SensorDataListResponse, 
    HealthCheckResponse,
    ErrorResponse,
    SensorDataQueryParams
)

# Logger konfigurieren
logger = logging.getLogger(__name__)

# Router mit Prefix und Tags
router = APIRouter(
    prefix="/sensors",
    tags=["sensors"],
    responses={
        404: {"model": ErrorResponse, "description": "Nicht gefunden"},
        500: {"model": ErrorResponse, "description": "Interner Server-Fehler"},
    }
)


@router.get(
    "/",
    response_model=List[SensorDataSchema],
    summary="Aktuelle Sensordaten abrufen",
    description="Ruft die neuesten Sensordaten ab, sortiert nach Zeitstempel (neueste zuerst)."
)
async def get_latest_sensor_data(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximale Anzahl zurückzugebende Datensätze"
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Anzahl zu überspringender Datensätze (Paginierung)"
    ),
    sensor_path: Optional[str] = Query(
        default=None,
        description="Filter nach spezifischem Sensor-Pfad"
    ),
    since: Optional[datetime] = Query(
        default=None,
        description="Nur Daten nach diesem Zeitstempel (ISO 8601)"
    ),
    until: Optional[datetime] = Query(
        default=None,
        description="Nur Daten vor diesem Zeitstempel (ISO 8601)"
    ),
    session: AsyncSession = Depends(get_session)
) -> List[SensorDataSchema]:
    """
    Ruft Sensordaten mit flexiblen Filteroptionen ab.
    
    Args:
        limit: Maximale Anzahl Datensätze (1-1000)
        offset: Überspringt die ersten N Datensätze
        sensor_path: Filtert nach spezifischem Sensor
        since: Nur Daten nach diesem Zeitpunkt
        until: Nur Daten vor diesem Zeitpunkt
        session: Datenbank-Session (automatisch injiziert)
        
    Returns:
        Liste der Sensordaten, sortiert nach Zeitstempel (neueste zuerst)
        
    Raises:
        HTTPException: Bei Datenbankfehlern oder ungültigen Parametern
    """
    try:
        # Base Query
        stmt = select(SensorData)
        
        # Filter anwenden
        conditions = []
        
        if sensor_path:
            conditions.append(SensorData.sensor_path == sensor_path)
            
        if since:
            conditions.append(SensorData.ts_collected >= since)
            
        if until:
            conditions.append(SensorData.ts_collected <= until)
            
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Sortierung und Limitierung
        stmt = (
            stmt
            .order_by(SensorData.ts_collected.desc())
            .offset(offset)
            .limit(limit)
        )
        
        # Ausführung
        result = await session.execute(stmt)
        sensor_data = list(result.scalars())
        
        logger.info(
            f"Sensordaten abgerufen: {len(sensor_data)} Datensätze "
            f"(limit={limit}, offset={offset}, sensor_path={sensor_path})"
        )
        
        return sensor_data
        
    except SQLAlchemyError as e:
        logger.error(f"Datenbankfehler beim Abrufen der Sensordaten: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fehler beim Abrufen der Sensordaten"
        ) from e
    except Exception as e:
        logger.error(f"Unerwarteter Fehler: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Interner Server-Fehler"
        ) from e


@router.get(
    "/summary",
    response_model=SensorDataListResponse,
    summary="Sensordaten mit Metadaten",
    description="Erweiterte Sensordaten-Abfrage mit zusätzlichen Metadaten."
)
async def get_sensor_data_summary(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    sensor_path: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session)
) -> SensorDataListResponse:
    """
    Ruft Sensordaten mit zusätzlichen Metadaten ab.
    
    Returns:
        Erweiterte Response mit Daten und Metadaten
    """
    try:
        # Hauptdaten abrufen (wiederverwendung der Logik)
        sensor_data = await get_latest_sensor_data(
            limit=limit,
            offset=offset, 
            sensor_path=sensor_path,
            session=session
        )
        
        # Metadaten sammeln
        sensor_paths = list(set(item.sensor_path for item in sensor_data))
        
        time_range = None
        if sensor_data:
            timestamps = [item.ts_collected for item in sensor_data]
            time_range = {
                "earliest": min(timestamps),
                "latest": max(timestamps)
            }
        
        return SensorDataListResponse(
            data=sensor_data,
            count=len(sensor_data),
            sensor_paths=sensor_paths,
            time_range=time_range
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Fehler beim Erstellen der Summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fehler beim Erstellen der Zusammenfassung"
        ) from e


@router.get(
    "/sensors",
    response_model=List[str],
    summary="Verfügbare Sensoren auflisten",
    description="Gibt eine Liste aller verfügbaren Sensor-Pfade zurück."
)
async def list_available_sensors(
    session: AsyncSession = Depends(get_session)
) -> List[str]:
    """
    Listet alle verfügbaren Sensor-Pfade auf.
    
    Returns:
        Liste der eindeutigen Sensor-Pfade
    """
    try:
        stmt = select(SensorData.sensor_path).distinct()
        result = await session.execute(stmt)
        sensor_paths = [row[0] for row in result.fetchall()]
        
        logger.info(f"Verfügbare Sensoren: {sensor_paths}")
        return sensor_paths
        
    except SQLAlchemyError as e:
        logger.error(f"Fehler beim Abrufen der Sensor-Liste: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fehler beim Abrufen der Sensor-Liste"
        ) from e


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health Check",
    description="Überprüft den Status der API und Datenbankverbindung."
)
async def health_check(
    session: AsyncSession = Depends(get_session)
) -> HealthCheckResponse:
    """
    Führt einen Health-Check der Anwendung durch.
    
    Returns:
        Health-Status mit Zeitstempel und Datenbankstatus
    """
    try:
        # Teste Datenbankverbindung mit einfacher Query
        stmt = select(func.count(SensorData.id))
        await session.execute(stmt)
        database_connected = True
        
    except Exception as e:
        logger.warning(f"Datenbankverbindung fehlgeschlagen: {e}")
        database_connected = False
    
    return HealthCheckResponse(
        status="healthy" if database_connected else "degraded",
        timestamp=datetime.now(),
        database_connected=database_connected
    )


@router.get(
    "/metrics",
    summary="Prometheus Metriken",
    description="Prometheus-Metriken für Monitoring und Grafana-Dashboards.",
    include_in_schema=False  # Nicht in OpenAPI-Docs anzeigen
)
async def get_metrics() -> Response:
    """
    Prometheus-Metriken Endpoint.
    
    Dieser Endpoint wird von Prometheus gescraped und stellt
    alle aktuellen Sensor-Metriken im Prometheus-Format bereit.
    
    Returns:
        Response: Prometheus-Metriken im Text-Format
    """
    try:
        metrics_data = get_prometheus_metrics()
        return Response(
            content=metrics_data,
            media_type=get_content_type()
        )
    except Exception as e:
        logger.error(f"Fehler beim Generieren der Prometheus-Metriken: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fehler beim Generieren der Metriken"
        ) from e 