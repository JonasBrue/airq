"""
SQLAlchemy Datenmodelle für das air-Q Backend.

Dieses Modul definiert die Datenbankstrukturen für die Speicherung
von Sensordaten mit optimierten Indexen und Constraints.
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import JSON, Column, DateTime, Integer, String, func, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid

from .database import Base


class SensorData(Base):
    """
    Modell für die Speicherung von air-Q Sensordaten.
    
    Diese Tabelle speichert die entschlüsselten und verarbeiteten Sensormesswerte.
    
    Attributes:
        id: Eindeutige Datensatz-ID (Primary Key)
        sensor_path: Identifikator des Sensors (z.B. '/livingroom')
        ts_collected: Zeitstempel der Datensammlung mit Zeitzone
        decoded_data: Entschlüsselte und strukturierte Messwerte
    """
    
    __tablename__ = "sensor_data"
    
    # Primary Key
    id = Column(
        Integer, 
        primary_key=True, 
        index=True
    )
    
    # Sensor-Identifikation
    sensor_path = Column(
        String(255), 
        nullable=False, 
        index=True
    )
    
    # Zeitstempel
    ts_collected = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Datenfelder
    decoded_data = Column(
        JSON,
        nullable=False
    )
    
    # Composite Index für häufige Abfragen
    __table_args__ = (
        Index('ix_sensor_data_path_time', 'sensor_path', 'ts_collected'),
        Index('ix_sensor_data_time_desc', ts_collected.desc()),
    )
    
    def __repr__(self) -> str:
        """String-Repräsentation für Debugging."""
        return (
            f"<SensorData(id={self.id}, "
            f"sensor_path='{self.sensor_path}', "
            f"ts_collected='{self.ts_collected}')>"
        )
    
    @property
    def temperature(self) -> float | None:
        """
        Hilfsmethode um Temperatur aus decoded_data zu extrahieren.
        
        Returns:
            Temperaturwert in Celsius oder None wenn nicht verfügbar
        """
        if self.decoded_data and 'temperature' in self.decoded_data:
            temp_data = self.decoded_data['temperature']
            # air-Q gibt [Wert, Fehler] zurück
            return temp_data[0] if isinstance(temp_data, list) else temp_data
        return None
    
    @property
    def humidity(self) -> float | None:
        """
        Hilfsmethode um Luftfeuchtigkeit aus decoded_data zu extrahieren.
        
        Returns:
            Luftfeuchtigkeit in % oder None wenn nicht verfügbar
        """
        if self.decoded_data and 'humidity' in self.decoded_data:
            humidity_data = self.decoded_data['humidity']
            return humidity_data[0] if isinstance(humidity_data, list) else humidity_data
        return None
    
    @property
    def co2(self) -> float | None:
        """
        Hilfsmethode um CO2-Wert aus decoded_data zu extrahieren.
        
        Returns:
            CO2-Konzentration in ppm oder None wenn nicht verfügbar
        """
        if self.decoded_data and 'co2' in self.decoded_data:
            co2_data = self.decoded_data['co2']
            return co2_data[0] if isinstance(co2_data, list) else co2_data
        return None 