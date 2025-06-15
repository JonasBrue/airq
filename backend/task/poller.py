"""
Background Tasks für das air-Q Backend.

Dieses Modul verwaltet das kontinuierliche Polling der air-Q Sensoren,
Datenentschlüsselung und Speicherung in der Datenbank.
"""

import asyncio
import base64
import http.client
import json
import logging
from typing import Any, Dict, Optional
import time

from Crypto.Cipher import AES
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from ..db.database import async_session
from ..db.models import SensorData
from ..metrics.prometheus_metrics import update_sensor_metrics

# Logger konfigurieren
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, settings.log_level))


class AirQCrypto:
    """
    Utility-Klasse für air-Q Verschlüsselung/Entschlüsselung.
    
    Kapselt die Kryptografie-Funktionen für bessere Wartbarkeit
    und Testbarkeit.
    """
    
    def __init__(self, password: str) -> None:
        """
        Initialisiert die Crypto-Instanz mit dem Passwort.
        
        Args:
            password: Das air-Q Passwort für die Entschlüsselung
        """
        self.password = password
        self._prepare_key()
    
    def _prepare_key(self) -> None:
        """Bereitet den AES-Schlüssel vor."""
        key = self.password.encode("utf-8")
        if len(key) < 32:
            key += b"0" * (32 - len(key))
        elif len(key) > 32:
            key = key[:32]
        self.key = key
    
    def _unpad(self, data: str) -> str:
        """Entfernt PKCS7-Padding von entschlüsselten Daten."""
        return data[: -ord(data[-1])]
    
    def decode_message(self, msgb64: str) -> Dict[str, Any]:
        """
        Entschlüsselt eine base64-kodierte air-Q Nachricht.
        
        Args:
            msgb64: Base64-kodierte verschlüsselte Nachricht
            
        Returns:
            Entschlüsselte Daten als Dictionary
            
        Raises:
            ValueError: Bei ungültigen Eingabedaten
            Exception: Bei Entschlüsselungsfehlern
        """
        try:
            msg = base64.b64decode(msgb64)
            cipher = AES.new(key=self.key, mode=AES.MODE_CBC, IV=msg[:16])
            decrypted = cipher.decrypt(msg[16:]).decode("utf-8")
            unpadded = self._unpad(decrypted)
            return json.loads(unpadded)
        except Exception as e:
            logger.error(f"Entschlüsselungsfehler: {e}")
            raise


class SensorPoller:
    """
    Klasse für das kontinuierliche Polling der air-Q Sensoren.
    
    Verwaltet HTTP-Verbindungen, Retry-Logic und Datenverarbeitung.
    """
    
    def __init__(self) -> None:
        """Initialisiert den Sensor-Poller."""
        self.crypto = AirQCrypto(settings.airq_password)
        self.host = settings.airq_host
        self.sensors = settings.airq_sensors
        self.poll_interval = settings.poll_interval_seconds
        self.max_retries = 3
        self.retry_delay = 5.0  # Sekunden
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
    
    async def fetch_sensor_data(self, sensor_path: str) -> Dict[str, Any]:
        """
        Ruft Daten von einem einzelnen Sensor ab.
        
        Args:
            sensor_path: Pfad des Sensors (z.B. '/livingroom')
            
        Returns:
            Dictionary mit raw_data und decoded_data
            
        Raises:
            Exception: Bei Verbindungs- oder Entschlüsselungsfehlern
        """
        loop = asyncio.get_running_loop()
        
        # HTTP-Request in Executor ausführen (blocking operation)
        def _fetch_sync() -> Dict[str, Any]:
            conn = http.client.HTTPSConnection(self.host, timeout=10)
            try:
                endpoint = f"{sensor_path}/data/" if not sensor_path.endswith('/') else f"{sensor_path}data/"
                conn.request("GET", endpoint)
                resp = conn.getresponse()
                
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status}: {resp.reason}")
                
                raw_response = json.loads(resp.read())
                
                # Entschlüsseln
                decoded_content = self.crypto.decode_message(raw_response["content"])
                
                return {
                    "raw_data": raw_response,
                    "decoded_data": decoded_content
                }
            finally:
                conn.close()
        
        return await loop.run_in_executor(None, _fetch_sync)
    
    async def store_sensor_data(self, sensor_path: str, data: Dict[str, Any]) -> None:
        """
        Speichert Sensordaten in der Datenbank und aktualisiert Prometheus-Metriken.
        
        Args:
            sensor_path: Pfad des Sensors
            data: Dictionary mit decoded_data
        """
        async with async_session() as session:
            try:
                record = SensorData(
                    sensor_path=sensor_path,
                    decoded_data=data["decoded_data"],
                )
                session.add(record)
                await session.commit()
                
                # Prometheus-Metriken aktualisieren
                update_sensor_metrics(sensor_path, data["decoded_data"])
                
                logger.debug(f"Sensordaten und Metriken aktualisiert: {sensor_path}")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Fehler beim Speichern von {sensor_path}: {e}")
                raise
    
    async def poll_single_sensor(self, sensor_path: str) -> bool:
        """
        Ruft Daten von einem Sensor ab und speichert sie.
        
        Args:
            sensor_path: Pfad des Sensors
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        retries = 0
        while retries <= self.max_retries:
            try:
                data = await self.fetch_sensor_data(sensor_path)
                await self.store_sensor_data(sensor_path, data)
                
                logger.info(f"Sensor {sensor_path} erfolgreich abgefragt")
                return True
                
            except Exception as e:
                retries += 1
                if retries <= self.max_retries:
                    logger.warning(
                        f"Fehler bei {sensor_path} (Versuch {retries}/{self.max_retries}): {e}"
                    )
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(
                        f"Sensor {sensor_path} nach {self.max_retries} Versuchen nicht erreichbar: {e}"
                    )
        
        return False
    
    async def poll_all_sensors(self) -> None:
        """Ruft Daten von allen konfigurierten Sensoren ab."""
        start_time = time.time()
        successful = 0
        
        # Parallel alle Sensoren abfragen
        tasks = [
            self.poll_single_sensor(sensor_path) 
            for sensor_path in self.sensors
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for sensor_path, result in zip(self.sensors, results):
            if isinstance(result, Exception):
                logger.error(f"Unerwarteter Fehler bei {sensor_path}: {result}")
            elif result:
                successful += 1
        
        duration = time.time() - start_time
        logger.info(
            f"Polling-Durchlauf abgeschlossen: {successful}/{len(self.sensors)} "
            f"Sensoren erfolgreich in {duration:.2f}s"
        )
    
    async def run(self) -> None:
        """
        Hauptschleife für das kontinuierliche Polling.
        
        Läuft bis zum Stoppen und pollt alle Sensoren in konfigurierten Intervallen.
        """
        self._running = True
        logger.info(
            f"Sensor-Polling gestartet: {len(self.sensors)} Sensoren, "
            f"Intervall: {self.poll_interval}s"
        )
        
        try:
            while self._running:
                cycle_start = time.time()
                
                await self.poll_all_sensors()
                
                # Berechne Wartezeit für nächsten Zyklus
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, self.poll_interval - cycle_duration)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(
                        f"Polling-Zyklus dauerte {cycle_duration:.2f}s, "
                        f"länger als Intervall ({self.poll_interval}s)"
                    )
                    
        except asyncio.CancelledError:
            logger.info("Sensor-Polling wurde abgebrochen")
            raise
        except Exception as e:
            logger.error(f"Kritischer Fehler im Polling: {e}")
            raise
        finally:
            self._running = False
            logger.info("Sensor-Polling beendet")
    
    def start(self) -> asyncio.Task[None]:
        """
        Startet das Polling als AsyncIO Task.
        
        Returns:
            Das AsyncIO Task-Objekt
        """
        if self._task and not self._task.done():
            logger.warning("Polling läuft bereits")
            return self._task
        
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self.run(), name="sensor-poller")
        return self._task
    
    async def stop(self) -> None:
        """Stoppt das Polling ordnungsgemäß."""
        if self._task and not self._task.done():
            self._running = False
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Sensor-Polling gestoppt")


# Globale Poller-Instanz
_poller: Optional[SensorPoller] = None


def get_poller() -> SensorPoller:
    """
    Singleton-Pattern für den Sensor-Poller.
    
    Returns:
        Die globale SensorPoller-Instanz
    """
    global _poller
    if _poller is None:
        _poller = SensorPoller()
    return _poller


def start_poller() -> asyncio.Task[None]:
    """
    Startet den Sensor-Poller.
    
    Returns:
        Das AsyncIO Task-Objekt für das Polling
    """
    poller = get_poller()
    return poller.start()


async def stop_poller(task: asyncio.Task[None]) -> None:
    """
    Stoppt den Sensor-Poller.
    
    Args:
        task: Das AsyncIO Task-Objekt des Pollers
    """
    poller = get_poller()
    await poller.stop() 