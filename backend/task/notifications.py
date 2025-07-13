"""
Notification Service für air-Q Alerts.

Dieses Modul verwaltet das Senden von Benachrichtigungen bei kritischen 
Luftqualitätswerten über verschiedene Kanäle (Telegram, etc.).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, Any
import httpx
from zoneinfo import ZoneInfo

from .config import settings

# Logger konfigurieren
logger = logging.getLogger(__name__)


class AlertManager:
    """
    Verwaltet das Senden von Alerts und Rate Limiting.
    
    Verhindert Spam-Benachrichtigungen durch Cooldown-Perioden
    und verwaltet verschiedene Notification-Kanäle.
    """
    
    def __init__(self):
        """Initialisiert den Alert Manager."""
        self.last_alerts: Dict[str, datetime] = {}
        self.active_alerts: Set[str] = set()
        self.consecutive_low_readings: Dict[str, int] = {}
        self.consecutive_high_readings: Dict[str, int] = {}
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # Logge Konfiguration beim Start
        logger.info(f"Alert Manager initialisiert - Min consecutive polls: {settings.min_consecutive_polls}, "
                   f"Health threshold: {settings.health_alert_threshold}, "
                   f"Cooldown: {settings.alert_cooldown_minutes}min, "
                   f"Telegram: {'enabled' if settings.telegram_enabled else 'disabled'}")
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Lazy-loading des HTTP-Clients."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=10.0)
        return self.http_client
    
    async def close(self) -> None:
        """Schließt den HTTP-Client."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
    
    def _get_alert_key(self, sensor_path: str, alert_type: str) -> str:
        """Generiert einen eindeutigen Alert-Key."""
        return f"{sensor_path}:{alert_type}"
    
    def _is_cooldown_active(self, alert_key: str) -> bool:
        """Prüft ob für diesen Alert noch ein Cooldown aktiv ist."""
        if alert_key not in self.last_alerts:
            return False
        
        last_alert = self.last_alerts[alert_key]
        cooldown_duration = timedelta(minutes=settings.alert_cooldown_minutes)
        
        return datetime.now(ZoneInfo("Europe/Berlin")) - last_alert < cooldown_duration
    
    def _mark_alert_sent(self, alert_key: str) -> None:
        """Markiert einen Alert als gesendet."""
        self.last_alerts[alert_key] = datetime.now(ZoneInfo("Europe/Berlin"))
        self.active_alerts.add(alert_key)
    
    def _clear_alert(self, alert_key: str) -> None:
        """Entfernt einen Alert aus der aktiven Liste."""
        self.active_alerts.discard(alert_key)
    
    async def send_telegram_message(self, message: str) -> bool:
        """
        Sendet eine Nachricht über Telegram.
        
        Args:
            message: Die zu sendende Nachricht
            
        Returns:
            True wenn erfolgreich gesendet, False bei Fehler
        """
        if not settings.telegram_enabled:
            logger.debug("Telegram nicht konfiguriert, überspringe Nachricht")
            return False
        
        try:
            client = await self._get_http_client()
            
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": settings.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                logger.info("Telegram-Nachricht erfolgreich gesendet")
                return True
            else:
                logger.error(f"Telegram API Fehler: {response.status_code} - {response.text}")
                return False
                
        except httpx.TimeoutException:
            logger.error("Telegram-Nachricht: Timeout beim Senden")
            return False
        except httpx.ConnectError:
            logger.error("Telegram-Nachricht: Verbindungsfehler")
            return False
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Senden der Telegram-Nachricht: {e}")
            return False
    
    async def send_health_alert(self, sensor_path: str, health_index: float) -> bool:
        """
        Sendet einen Gesundheitsindex-Alert nach erforderlicher Anzahl konsekutiver niedriger Messwerte.
        
        Args:
            sensor_path: Pfad des betroffenen Sensors
            health_index: Aktueller Gesundheitsindex
            
        Returns:
            True wenn Alert gesendet wurde, False wenn übersprungen
        """
        alert_key = self._get_alert_key(sensor_path, "health_low")
        
        # Setze Zähler für konsekutive hohe Messwerte zurück
        old_high_count = self.consecutive_high_readings.get(sensor_path, 0)
        self.consecutive_high_readings[sensor_path] = 0
        if old_high_count > 0:
            logger.info(f"High readings counter zurückgesetzt für {sensor_path}: {old_high_count} -> 0")
        
        # Erhöhe Zähler für konsekutive niedrige Messwerte
        current_count = self.consecutive_low_readings.get(sensor_path, 0)
        self.consecutive_low_readings[sensor_path] = current_count + 1
        new_count = self.consecutive_low_readings[sensor_path]
        
        # Logge immer den aktuellen Stand
        logger.info(f"Health Alert Counter für {sensor_path}: {new_count}/{settings.min_consecutive_polls} (Health: {health_index}, Threshold: {settings.health_alert_threshold})")
        
        # Prüfe ob genug konsekutive niedrige Messwerte erreicht wurden
        if new_count < settings.min_consecutive_polls:
            logger.debug(f"Noch {settings.min_consecutive_polls - new_count} konsekutive niedrige Messwerte nötig für {sensor_path}")
            return False
        
        # Prüfe Cooldown nur wenn wir bereit sind zu senden
        if self._is_cooldown_active(alert_key):
            logger.info(f"Health Alert für {sensor_path} im Cooldown, überspringe (Counter bleibt bei {new_count})")
            return False
        
        # Erstelle Alert-Nachricht
        message = self._format_health_alert(sensor_path, health_index)
        
        # Sende Nachricht
        success = await self.send_telegram_message(message)
        
        if success:
            self._mark_alert_sent(alert_key)
            logger.warning(f"Health Alert gesendet für {sensor_path}: {health_index} (nach {new_count} konsekutiven niedrigen Messwerten)")
            return True
        else:
            logger.error(f"Fehler beim Senden des Health Alerts für {sensor_path}")
        
        return False
    
    async def send_health_recovery(self, sensor_path: str, health_index: float) -> bool:
        """
        Sendet eine Entwarnung wenn sich der Gesundheitsindex nach erforderlicher Anzahl konsekutiver guter Messwerte erholt hat.
        
        Args:
            sensor_path: Pfad des betroffenen Sensors
            health_index: Aktueller Gesundheitsindex
            
        Returns:
            True wenn Entwarnung gesendet wurde
        """
        alert_key = self._get_alert_key(sensor_path, "health_low")
        
        # Setze Zähler für konsekutive niedrige Messwerte zurück
        old_low_count = self.consecutive_low_readings.get(sensor_path, 0)
        self.consecutive_low_readings[sensor_path] = 0
        if old_low_count > 0:
            logger.info(f"Low readings counter zurückgesetzt für {sensor_path}: {old_low_count} -> 0")
        
        # Erhöhe Zähler für konsekutive hohe Messwerte
        current_high_count = self.consecutive_high_readings.get(sensor_path, 0)
        self.consecutive_high_readings[sensor_path] = current_high_count + 1
        new_high_count = self.consecutive_high_readings[sensor_path]
        
        # Logge immer den aktuellen Stand
        logger.info(f"Health Recovery Counter für {sensor_path}: {new_high_count}/{settings.min_consecutive_polls} (Health: {health_index}, Threshold: {settings.health_alert_threshold})")
        
        # Prüfe ob genug konsekutive hohe Messwerte erreicht wurden
        if new_high_count < settings.min_consecutive_polls:
            logger.debug(f"Noch {settings.min_consecutive_polls - new_high_count} konsekutive hohe Messwerte nötig für Recovery von {sensor_path}")
            return False
        
        # Nur senden wenn vorher ein Alert aktiv war
        if alert_key not in self.active_alerts:
            logger.debug(f"Kein aktiver Alert für {sensor_path}, überspringe Recovery (Counter bleibt bei {new_high_count})")
            return False
        
        # Entferne Alert aus aktiver Liste
        self._clear_alert(alert_key)
        
        # Erstelle Entwarnung
        message = self._format_health_recovery(sensor_path, health_index)
        
        # Sende Nachricht
        success = await self.send_telegram_message(message)
        
        if success:
            logger.info(f"Health Recovery gesendet für {sensor_path}: {health_index} (nach {new_high_count} konsekutiven hohen Messwerten)")
            return True
        else:
            logger.error(f"Fehler beim Senden der Health Recovery für {sensor_path}")
            # Alert wieder als aktiv markieren bei Sendefehler
            self.active_alerts.add(alert_key)
        
        return False
    
    def reset_consecutive_low_readings(self, sensor_path: str) -> None:
        """
        Setzt den Zähler für konsekutive niedrige Messwerte zurück.
        
        Args:
            sensor_path: Pfad des betroffenen Sensors
        """
        old_count = self.consecutive_low_readings.get(sensor_path, 0)
        self.consecutive_low_readings[sensor_path] = 0
        if old_count > 0:
            logger.info(f"Low readings counter zurückgesetzt für {sensor_path}: {old_count} -> 0")
    
    def reset_consecutive_high_readings(self, sensor_path: str) -> None:
        """
        Setzt den Zähler für konsekutive hohe Messwerte zurück.
        
        Args:
            sensor_path: Pfad des betroffenen Sensors
        """
        old_count = self.consecutive_high_readings.get(sensor_path, 0)
        self.consecutive_high_readings[sensor_path] = 0
        if old_count > 0:
            logger.info(f"High readings counter zurückgesetzt für {sensor_path}: {old_count} -> 0")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Gibt den aktuellen Status aller Counter und aktiven Alerts zurück.
        
        Returns:
            Dictionary mit Status-Informationen
        """
        return {
            "consecutive_low_readings": dict(self.consecutive_low_readings),
            "consecutive_high_readings": dict(self.consecutive_high_readings),
            "active_alerts": list(self.active_alerts),
            "last_alerts": {k: v.isoformat() for k, v in self.last_alerts.items()},
            "config": {
                "min_consecutive_polls": settings.min_consecutive_polls,
                "health_alert_threshold": settings.health_alert_threshold,
                "alert_cooldown_minutes": settings.alert_cooldown_minutes,
                "telegram_enabled": settings.telegram_enabled
            }
        }
    
    def log_status(self) -> None:
        """Loggt den aktuellen Status des Alert-Systems."""
        status = self.get_status()
        logger.info(f"Alert Manager Status: {status}")
    
    def cleanup_old_data(self) -> None:
        """
        Bereinigt alte Daten aus den Countern und Alert-Listen.
        
        Entfernt Counter für Sensoren, die nicht mehr in der Konfiguration stehen,
        und alte Alert-Einträge, die länger als das doppelte Cooldown-Intervall zurückliegen.
        """
        configured_sensors = set(settings.airq_sensors)
        
        # Entferne Counter für nicht mehr konfigurierte Sensoren
        old_low_sensors = set(self.consecutive_low_readings.keys()) - configured_sensors
        old_high_sensors = set(self.consecutive_high_readings.keys()) - configured_sensors
        
        for sensor in old_low_sensors:
            del self.consecutive_low_readings[sensor]
            logger.info(f"Bereinigt low readings counter für entfernten Sensor: {sensor}")
        
        for sensor in old_high_sensors:
            del self.consecutive_high_readings[sensor]
            logger.info(f"Bereinigt high readings counter für entfernten Sensor: {sensor}")
        
        # Entferne sehr alte Alert-Einträge (älter als doppeltes Cooldown-Intervall)
        cutoff_time = datetime.now(ZoneInfo("Europe/Berlin")) - timedelta(minutes=settings.alert_cooldown_minutes * 2)
        old_alerts = [key for key, timestamp in self.last_alerts.items() if timestamp < cutoff_time]
        
        for alert_key in old_alerts:
            del self.last_alerts[alert_key]
            logger.debug(f"Bereinigt alten Alert-Eintrag: {alert_key}")
    
    def _format_health_alert(self, sensor_path: str, health_index: float) -> str:
        """Formatiert eine Gesundheitsindex-Warnung."""
        return f"""🚨 *Luftqualitäts-Warnung*

**Sensor:** `{sensor_path}`
**Gesundheitsindex:** {health_index:.0f}/1000
**Schwellenwert:** {settings.health_alert_threshold}

Die Luftqualität ist nach {settings.min_consecutive_polls} konsekutiven Messungen unter den kritischen Wert gefallen!"""
    
    def _format_health_recovery(self, sensor_path: str, health_index: float) -> str:
        """Formatiert eine Entwarnung."""
        return f"""✅ *Entwarnung - Luftqualität verbessert*

**Sensor:** `{sensor_path}`
**Gesundheitsindex:** {health_index:.0f}/1000
**Schwellenwert:** {settings.health_alert_threshold}

Die Luftqualität hat sich nach {settings.min_consecutive_polls} konsekutiven Messungen wieder normalisiert."""


# Globale Alert Manager Instanz
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """
    Singleton-Pattern für den Alert Manager.
    
    Returns:
        Die globale AlertManager-Instanz
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


async def cleanup_alert_manager() -> None:
    """Bereinigt den Alert Manager beim Shutdown."""
    global _alert_manager
    if _alert_manager:
        await _alert_manager.close()
        _alert_manager = None 