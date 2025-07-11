"""
Zentrale Konfiguration für das air-Q Backend.

Diese Datei verwaltet alle Umgebungsvariablen und Konfigurationseinstellungen
für eine bessere Wartbarkeit und Typsicherheit.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from dotenv import load_dotenv

# .env Datei frühzeitig laden
load_dotenv()


class Settings(BaseSettings):
    """Zentrale Anwendungskonfiguration mit Pydantic-Validierung."""
    
    # Datenbank-Konfiguration
    database_url: str = "postgresql+asyncpg://airq:airq@db:5432/airq"
    
    # air-Q Sensor-Konfiguration  
    airq_host: str
    airq_password: str
    airq_sensors: str
    poll_interval_seconds: float = 1.5
    
    # API-Konfiguration
    cors_origins: List[str] = Field(default=["http://localhost:3000"])
    api_title: str = Field(default="air-Q Daten-Service")
    api_version: str = Field(default="1.0.0")
    
    # Logging
    log_level: str = Field(default="INFO")
    
    # Telegram Alerting Configuration
    telegram_bot_token: Optional[str] = Field(default=None)
    telegram_chat_id: Optional[str] = Field(default=None)
    health_alert_threshold: int = Field(default=100)
    alert_cooldown_minutes: int = Field(default=30)
    
    @field_validator('airq_sensors')
    def parse_sensors(cls, v: str) -> List[str]:
        """Konvertiert die Sensor-String-Liste in eine echte Liste."""
        if not v:
            raise ValueError("AIRQ_SENSORS darf nicht leer sein")
        return [sensor.strip() for sensor in v.split(",") if sensor.strip()]
    
    @field_validator('airq_host')
    def validate_host(cls, v: str) -> str:
        """Validiert dass der Host gesetzt ist."""
        if not v.strip():
            raise ValueError("AIRQ_HOST ist erforderlich")
        return v.strip()
    
    @field_validator('airq_password')
    def validate_password(cls, v: str) -> str:
        """Validiert dass das Passwort gesetzt ist."""
        if not v.strip():
            raise ValueError("AIRQ_PASSWORD ist erforderlich")
        return v.strip()
    
    @property
    def telegram_enabled(self) -> bool:
        """Prüft ob Telegram-Alerting aktiviert ist."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False
    )


# Globale Settings-Instanz
settings = Settings() 