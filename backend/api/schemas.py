"""
Pydantic Schemas für die air-Q API.

Dieses Modul definiert die Datenstrukturen für API-Requests und -Responses
mit automatischer Validierung und Serialisierung.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, validator


class SensorDataSchema(BaseModel):
    """
    Schema für einzelne Sensordaten-Responses.
    
    Dieses Schema definiert die Struktur der API-Antworten für Sensordaten.
    Es enthält nur die für Clients relevanten Felder und versteckt
    interne/sensible Daten wie raw_data.
    
    Attributes:
        id: Eindeutige Datensatz-ID
        sensor_path: Pfad/Identifikator des Sensors
        ts_collected: Zeitstempel der Datensammlung
        decoded_data: Entschlüsselte Sensormesswerte
    """
    
    id: int = Field(
        ..., 
        description="Eindeutige Datensatz-ID",
        example=123
    )
    
    sensor_path: str = Field(
        ..., 
        description="Pfad oder Identifikator des Sensors",
        example="/livingroom"
    )
    
    ts_collected: datetime = Field(
        ..., 
        description="Zeitstempel der Datensammlung (ISO 8601 mit Zeitzone)",
        example="2024-01-15T10:30:00+00:00"
    )
    
    decoded_data: Dict[str, Any] = Field(
        ..., 
        description="Entschlüsselte Sensormesswerte als JSON-Objekt",
        example={
            "temperature": [23.5, 0.2],
            "humidity": [45.2, 1.1], 
            "co2": [420, 15]
        }
    )
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 123,
                "sensor_path": "/livingroom", 
                "ts_collected": "2024-01-15T10:30:00+00:00",
                "decoded_data": {
                    "temperature": [23.5, 0.2],
                    "humidity": [45.2, 1.1],
                    "co2": [420, 15],
                    "timestamp": 1705315800000
                }
            }
        }
    )


class SensorDataListResponse(BaseModel):
    """
    Schema für Listen-Responses mit Metadaten.
    
    Erweiterte Response-Struktur die zusätzliche Metadaten
    über die zurückgegebenen Daten enthält.
    """
    
    data: List[SensorDataSchema] = Field(
        ...,
        description="Liste der Sensordaten"
    )
    
    count: int = Field(
        ...,
        description="Anzahl der zurückgegebenen Datensätze"
    )
    
    sensor_paths: List[str] = Field(
        ...,
        description="Liste aller in den Daten vorkommenden Sensor-Pfade"
    )
    
    time_range: Optional[Dict[str, datetime]] = Field(
        None,
        description="Zeitraum der Daten (earliest/latest)"
    )


class HealthCheckResponse(BaseModel):
    """Schema für Health-Check Responses."""
    
    status: str = Field(
        ...,
        description="Status der Anwendung",
        example="healthy"
    )
    
    timestamp: datetime = Field(
        ...,
        description="Zeitstempel des Health-Checks"
    )
    
    database_connected: bool = Field(
        ...,
        description="Status der Datenbankverbindung"
    )


class ErrorResponse(BaseModel):
    """Schema für Fehler-Responses."""
    
    detail: str = Field(
        ...,
        description="Detaillierte Fehlerbeschreibung"
    )
    
    error_code: Optional[str] = Field(
        None,
        description="Anwendungsspezifischer Fehlercode"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Zeitstempel des Fehlers"
    )


# Query Parameter Schemas
class SensorDataQueryParams(BaseModel):
    """
    Schema für Query-Parameter bei Sensordaten-Abfragen.
    
    Ermöglicht typisierte und validierte Query-Parameter
    für flexiblere API-Abfragen.
    """
    
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximale Anzahl zurückzugebender Datensätze"
    )
    
    offset: int = Field(
        default=0,
        ge=0,
        description="Anzahl zu überspringender Datensätze (für Paginierung)"
    )
    
    sensor_path: Optional[str] = Field(
        None,
        description="Filter nach spezifischem Sensor-Pfad"
    )
    
    since: Optional[datetime] = Field(
        None,
        description="Nur Daten nach diesem Zeitstempel"
    )
    
    until: Optional[datetime] = Field(
        None,
        description="Nur Daten vor diesem Zeitstempel"
    )
    
    @validator('until')
    def validate_time_range(cls, v: Optional[datetime], values: Dict[str, Any]) -> Optional[datetime]:
        """Validiert dass 'until' nach 'since' liegt."""
        if v and 'since' in values and values['since']:
            if v <= values['since']:
                raise ValueError("'until' muss nach 'since' liegen")
        return v 