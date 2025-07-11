"""
Notification Service für air-Q Alerts.

Dieses Modul verwaltet das Senden von Benachrichtigungen bei kritischen 
Luftqualitätswerten über verschiedene Kanäle (Telegram, etc.).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
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
        self.http_client: Optional[httpx.AsyncClient] = None
    
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
                
        except Exception as e:
            logger.error(f"Fehler beim Senden der Telegram-Nachricht: {e}")
            return False
    
    async def send_health_alert(self, sensor_path: str, health_index: float) -> bool:
        """
        Sendet einen Gesundheitsindex-Alert.
        
        Args:
            sensor_path: Pfad des betroffenen Sensors
            health_index: Aktueller Gesundheitsindex
            
        Returns:
            True wenn Alert gesendet wurde, False wenn übersprungen
        """
        alert_key = self._get_alert_key(sensor_path, "health_low")
        
        # Prüfe Cooldown
        if self._is_cooldown_active(alert_key):
            logger.debug(f"Health Alert für {sensor_path} im Cooldown")
            return False
        
        # Erstelle Alert-Nachricht
        message = self._format_health_alert(sensor_path, health_index)
        
        # Sende Nachricht
        success = await self.send_telegram_message(message)
        
        if success:
            self._mark_alert_sent(alert_key)
            logger.warning(f"Health Alert gesendet für {sensor_path}: {health_index}")
            return True
        
        return False
    
    async def send_health_recovery(self, sensor_path: str, health_index: float) -> bool:
        """
        Sendet eine Entwarnung wenn sich der Gesundheitsindex erholt hat.
        
        Args:
            sensor_path: Pfad des betroffenen Sensors
            health_index: Aktueller Gesundheitsindex
            
        Returns:
            True wenn Entwarnung gesendet wurde
        """
        alert_key = self._get_alert_key(sensor_path, "health_low")
        
        # Nur senden wenn vorher ein Alert aktiv war
        if alert_key not in self.active_alerts:
            return False
        
        # Entferne Alert aus aktiver Liste
        self._clear_alert(alert_key)
        
        # Erstelle Entwarnung
        message = self._format_health_recovery(sensor_path, health_index)
        
        # Sende Nachricht
        success = await self.send_telegram_message(message)
        
        if success:
            logger.info(f"Health Recovery gesendet für {sensor_path}: {health_index}")
            return True
        
        return False
    
    def _format_health_alert(self, sensor_path: str, health_index: float) -> str:
        """Formatiert eine Gesundheitsindex-Warnung."""
        return f"""🚨 *Luftqualitäts-Warnung*

**Sensor:** `{sensor_path}`
**Gesundheitsindex:** {health_index:.0f}/1000
**Schwellenwert:** {settings.health_alert_threshold}

Die Luftqualität ist unter den kritischen Wert gefallen!"""
    
    def _format_health_recovery(self, sensor_path: str, health_index: float) -> str:
        """Formatiert eine Entwarnung."""
        return f"""✅ *Entwarnung - Luftqualität verbessert*

**Sensor:** `{sensor_path}`
**Gesundheitsindex:** {health_index:.0f}/1000
**Schwellenwert:** {settings.health_alert_threshold}

Die Luftqualität hat sich wieder normalisiert."""


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